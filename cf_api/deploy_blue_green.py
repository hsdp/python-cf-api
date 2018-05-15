import os
from .deploy_manifest import log
from . import exceptions as exc


class BlueGreen(object):
    """This class orchestrates a Blue-Green deployment in the style of the
    Autopilot CF CLI plugin.
    """

    def __init__(self,
                 space,
                 manifest,
                 verbose=True,
                 wait_kwargs=None,
                 **kwargs):
        """Initializes the deployment

        Args:
            space (cf_api.deploy_space.Space):
                The space to which the application should be deployed
            manifest (cf_api.deploy_manifest.Deploy):
                The manifest of the application to be deployed
            verbose (bool):
                Whether the deployment should be verbose in its output
            wait_kwargs (dict|None):
                Arguments to pass to the application ``wait_for_app_start``
                function when waiting for the application to start
        """
        self.space = space
        self.manifest = manifest
        self.verbose = verbose
        self.venerable_name = '-'.join([self.app_name, 'venerable'])
        self.venerable_manifest = self.manifest.clone(self.venerable_name)
        self.app = None
        self.venerable_app = None
        self.wait_kwargs = wait_kwargs or {}

    @property
    def cc(self):
        return self.space.cc

    @property
    def app_name(self):
        return self.manifest.name

    @classmethod
    def parse_manifest(cls, space, manifest_filename, **kwargs):
        """Parses a deployment manifest and creates a BlueGreen instance
        for each application in the manifest.

        Args:
            space (cf_api.deploy_space.Space):
                space to which the manifest should be deployed
            manifest_filename (str):
                application manifest to be deployed
            **kwargs (dict):
                passed into the BlueGreen constructor

        Returns:
            list[BlueGreen]
        """
        space.set_debug(kwargs.get('verbose'))
        manifests = space.get_deploy_manifest(manifest_filename)
        return [BlueGreen(space, manifest, **kwargs) for manifest in manifests]

    def log(self, *args):
        if self.verbose:
            return log(*args)

    def _load_apps(self):
        self._load_app()
        self._load_venerable_app()

    def _load_app(self):
        try:
            self.app = self.space.get_app_by_name(self.app_name)
        except exc.ResponseException as e:
            self.app = None
            if 404 != e.code:
                raise

    def _load_venerable_app(self):
        try:
            self.venerable_app = self.space.get_app_by_name(
                    self.venerable_name)
        except exc.ResponseException as e:
            self.venerable_app = None
            if 404 != e.code:
                raise

    def _rename_app(self):
        self._load_app()
        if self.app:
            self._load_venerable_app()
            if self.venerable_app:
                raise exc.InvalidStateException(
                    'attempting to rename app to venerable, but venerable '
                    'already exists', 409)
            return self.cc.apps(self.app.guid)\
                    .set_params(name=self.venerable_name).put().data
        self._load_apps()
        return None

    def _destroy_venerable_app(self):
        self._load_venerable_app()
        if self.venerable_app:
            self._load_app()
            if not self.app:
                raise exc.InvalidStateException(
                    'attempting to destroy venerable app, but no app will take'
                    ' it\'s place! aborting...', 409)
            return self.venerable_manifest.destroy(destroy_routes=False)
        self._load_apps()
        return None

    def wait_and_cleanup(self):
        """Waits for the new application to start and then destroys the old
        version of the app.
        """
        self.log('Waiting for app to start...')
        self.manifest.wait_for_app_start(
            tailing=self.verbose, **self.wait_kwargs)
        self.log('OK')
        self.log('Destroying venerable...')
        self._load_venerable_app()
        if self.venerable_app:
            self._destroy_venerable_app()
        self.log('OK')

    def deploy_app(self):
        """Deploys the new application
        """
        self.log('Checking apps...')
        self._load_apps()
        self.log('OK')

        if self.venerable_app:
            if self.app:
                self.log('Leftover venerable detected with replacement! '
                         'Deleting...')
                self._destroy_venerable_app()
                self.log('OK')
            else:
                self.log('Leftover venerable detected with no replacement! '
                         'Aborting...')
                raise exc.InvalidStateException(
                    'Leftover venerable detected! Rename it and try again.',
                    409)

        if self.app:
            self.log('Renaming app to venerable...')
            self._rename_app()
            self.log('OK')

        self.manifest.push()

    def deploy(self):
        """Deploy the new application, wait for it to start, then clean up the
        old application.
        """
        self.deploy_app()
        self.wait_and_cleanup()


def main():
    import argparse
    from getpass import getpass
    from .deploy_space import Space
    import cf_api
    args = argparse.ArgumentParser()
    args.add_argument('--cloud-controller', required=True)
    args.add_argument('-u', '--user')
    args.add_argument('-o', '--org', required=True)
    args.add_argument('-s', '--space', required=True)
    args.add_argument('-m', '--manifest', required=True)
    args = args.parse_args()

    kwargs = dict(
        client_id='cf',
        client_secret='',
    )
    if args.user:
        kwargs['username'] = args.user
        kwargs['password'] = getpass()
    else:
        kwargs['refresh_token'] = os.getenv('CF_REFRESH_TOKEN', '')

    cc = cf_api.new_cloud_controller(args.cloud_controller, **kwargs)
    space = Space(cc, org_name=args.org, space_name=args.space).set_debug(True)
    for manifest in space.deploy_blue_green(args.manifest):
        pass
    for manifest in space.wait_blue_green(args.manifest):
        pass


if '__main__' == __name__:
    main()
