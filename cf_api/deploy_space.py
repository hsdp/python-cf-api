from __future__ import print_function
import json
from . import deploy_manifest
from . import deploy_service
from . import exceptions as exc


class Space(object):
    """This class provides support for working with a particular space. It
    mainly provides convenience functions for deploying, fetching, and
    destroying the space, apps, and services.
    """

    _org = None
    _space = None
    _space_name = None

    _debug = False

    def __init__(self,
                 cc,
                 org_name=None,
                 org_guid=None,
                 space_name=None,
                 space_guid=None,
                 is_debug=None):
        self.cc = cc
        if space_guid:
            self.set_space_guid(space_guid)
        elif org_guid:
            self.set_org_guid(org_guid)
        elif org_name and space_name:
            self.set_org(org_name).set_space(space_name)
        elif org_name:
            self.set_org(org_name)

        if is_debug is not None:
            self.set_debug(is_debug)

    @property
    def space(self):
        """Returns the currently set space
        """
        if not self._space:
            if not self._space_name:
                raise exc.InvalidStateException('Space is not set.', 500)
            else:
                self.set_space(self._space_name)
        return self._space

    @property
    def org(self):
        """Returns the currently set org
        """
        if not self._org:
            raise exc.InvalidStateException('Org is not set.', 500)
        return self._org

    def set_org(self, org_name):
        """Sets the organization name for this space

        Args:
            org_name (str): name of the organization

        Returns:
            space (Space): self
        """
        res = self.cc.organizations().get_by_name(org_name)
        self._org = res.resource
        if self._org is None:
            raise exc.InvalidStateException('Org not found.', 404)
        return self

    def set_space(self, space_name):
        """Sets the space name

        Args:
            space_name (str): name of the space

        Returns:
            space (Space): self
        """
        if not self._org:
            raise exc.InvalidStateException(
                'Org is required to set the space name.', 500)
        res = self.cc.request(self._org.spaces_url).get_by_name(space_name)
        self._space = res.resource
        self._space_name = space_name
        return self

    def set_org_guid(self, org_guid):
        """Sets and loads the organization by the given GUID
        """
        res = self.cc.organizations(org_guid).get()
        self._org = res.resource
        return self

    def set_space_guid(self, space_guid):
        """Sets the GUID of the space to be used in this deployment

        Args:
            space_guid (str): guid of the space

        Returns:
            self (Space)
        """
        res = self.cc.spaces(space_guid).get()
        self._space = res.resource

        res = self.cc.request(self._space.organization_url).get()
        self._org = res.resource
        return self

    def set_debug(self, debug):
        """Sets a debug flag on whether this client should print debug messages

        Args:
            debug (bool)

        Returns:
            self (Space)
        """
        self._debug = debug
        return self

    def request(self, *urls):
        """Creates a request object with a base url (i.e. /v2/spaces/<id>)
        """
        return self.cc.request(self._space['metadata']['url'], *urls)

    def create(self, **params):
        """Creates the space

        Keyword Args:
            params: HTTP body args for the space create endpoint
        """
        if not self._space:
            res = self.cc.spaces().set_params(
                name=self._space_name,
                organization_guid=self._org.guid,
                **params
            ).post()

            self._space = res.resource

        return self._space

    def destroy(self, destroy_routes=False):
        """Destroys the space, and, optionally, any residual routes existing in
        the space.

        Keyword Args:
            destroy_routes (bool): indicates if to destroy routes
        """
        if not self._space:
            raise exc.InvalidStateException(
                'No space specified. Can\'t destroy.', 500)

        route_results = []
        if destroy_routes:
            for r in self.get_routes():
                res = self.cc.routes(r.guid).delete()
                route_results.append(res.data)

        res = self.cc.spaces(self._space.guid).delete()
        self._space = None
        return res.resource, route_results

    def get_deploy_manifest(self, manifest_filename):
        """Parses the manifest deployment list and sets the org and space to be
        used in deployment.
        """
        self._assert_space()
        app_deploys = deploy_manifest.Deploy\
            .parse_manifest(manifest_filename, self.cc)
        return [d.set_org_and_space_dicts(self._org, self._space)
                 .set_debug(self._debug) for d in app_deploys]

    def get_deploy_service(self):
        """Returns a service deployment client with the org and space to be
        used in deployment.
        """
        self._assert_space()
        return deploy_service.DeployService(self.cc)\
            .set_debug(self._debug)\
            .set_org_and_space_dicts(self._org, self._space)

    def deploy_manifest(self, manifest_filename, **kwargs):
        """Deploys all apps in the given app manifest into this space.

        Args:
            manifest_filename (str): app manifest filename to be deployed
        """
        return [m.push(**kwargs)
                for m in self.get_deploy_manifest(manifest_filename)]

    def wait_manifest(self, manifest_filename, interval=20, timeout=300,
                      tailing=False):
        """Waits for an app to start given a manifest filename.

        Args:
            manifest_filename (str): app manifest filename to be waited on

        Keyword Args:
            interval (int): how often to check if the app has started
            timeout (int): how long to wait for the app to start
        """
        app_deploys = self.get_deploy_manifest(manifest_filename)
        deploy_manifest.Deploy.wait_for_apps_start(
            app_deploys, interval, timeout, tailing=tailing)

    def destroy_manifest(self, manifest_filename, destroy_routes=False):
        """Destroys all apps in the given app manifest in this space.

        Args:
            manifest_filename (str): app manifest filename to be destroyed

        Keyword Args:
            destroy_routes (bool): indicates whether to destroy routes
        """
        return [m.destroy(destroy_routes)
                for m in self.get_deploy_manifest(manifest_filename)]

    def get_blue_green(self, manifest_filename, interval=20, timeout=300,
                       tailing=None, **kwargs):
        """Parses the manifest and searches for ``app_name``, returning an
        instance of the BlueGreen deployer object.

        Args:
            manifest_filename (str)
            interval (int)
            timeout (int)
            tailing (bool)
            **kwargs (dict): are passed along to the BlueGreen constructor

        Returns:
            list[cf_api.deploy_blue_green.BlueGreen]
        """
        from .deploy_blue_green import BlueGreen
        if tailing is not None:
            kwargs['verbose'] = tailing
        elif 'verbose' not in kwargs:
            kwargs['verbose'] = self._debug
        kwargs['wait_kwargs'] = {'interval': interval, 'timeout': timeout}
        return BlueGreen.parse_manifest(self, manifest_filename, **kwargs)

    def deploy_blue_green(self, manifest_filename, **kwargs):
        """Deploys the application from the given manifest using the
        BlueGreen deployment strategy

        Args:
            manifest_filename (str)
            **kwargs (dict): are passed along to self.get_blue_green

        Returns:
            list
        """
        return [m.deploy_app()
                for m in self.get_blue_green(manifest_filename, **kwargs)]

    def wait_blue_green(self, manifest_filename, **kwargs):
        """Waits for the application to start, from the given manifest using
        the BlueGreen deployment strategy

        Args:
            manifest_filename (str)
            **kwargs (dict): are passed along to self.get_blue_green

        Returns:
            list
        """
        return [m.wait_and_cleanup()
                for m in self.get_blue_green(manifest_filename, **kwargs)]

    def get_service_instance_by_name(self, name):
        """Searches the space for a service instance with the name
        """
        res = self.cc.request(self._space.service_instances_url)\
            .get_by_name(name)
        return res.resource

    def get_app_by_name(self, name):
        """Searches the space for an app with the name
        """
        res = self.cc.request(self._space.apps_url)\
            .get_by_name(name)
        return res.resource

    def get_routes(self, host=None):
        """Searches the space for routes
        """
        req = self.cc.spaces(self._space.guid, 'routes')
        res = req.get_by_name(host, 'host') if host else req.get()
        return res.resources

    def _assert_space(self):
        if not self._space:
            raise exc.InvalidStateException('No space is set.', 500)


if '__main__' == __name__:
    import argparse
    import __init__ as cf_api
    from getpass import getpass

    def main():
        args = argparse.ArgumentParser(
                description='This tool performs Cloud Controller API requests '
                            'on behalf of a user in a given org/space. It may '
                            'be used to look up space specific resources such '
                            'as apps and services. It returns only the raw '
                            'JSON response from the Cloud Controller.')
        args.add_argument(
            '--cloud-controller', dest='cloud_controller', required=True,
            help='The Cloud Controller API endpoint '
                 '(excluding leading slashes)')
        args.add_argument(
            '-u', '--user', dest='user', required=True,
            help='The user used to authenticate. This may be omitted '
                 'if --client-id and --client-secret have sufficient '
                 'authorization to perform the desired request without a '
                 'user\'s permission')
        args.add_argument(
            '-o', '--org', dest='org', required=True,
            help='The organization to be accessed')
        args.add_argument(
            '-s', '--space', dest='space', required=True,
            help='The space to be accessed')
        args.add_argument(
            '--client-id', dest='client_id', default='cf',
            help='Used to set a custom client ID')
        args.add_argument(
            '--client-secret', dest='client_secret', default='',
            help='Secret corresponding to --client-id')
        args.add_argument(
            '--skip-ssl', dest='skip_ssl', action='store_true',
            help='Indicates to skip SSL cert verification.')
        args.add_argument(
            '--show-org', dest='show_org', action='store_true',
            help='Indicates to show the organization set in --org/-o')
        args.add_argument(
            '--list-all', dest='list_all', action='store_true',
            help='Indicates to get all pages of resources matching the given '
                 'URL')
        args.add_argument(
            '--pretty', dest='pretty_print', action='store_true',
            help='Indicates to pretty-print the resulting JSON')
        args.add_argument(
            'url', nargs='?',
            help='The URL to be accessed relative to the space URL. This value'
                 ' will be appended to the space URL indicated by -o and -s '
                 '(i.e. /spaces/<space_guid>/<url>)')
        args = args.parse_args()

        cc = cf_api.new_cloud_controller(
            args.cloud_controller,
            username=args.user,
            password=getpass().strip() if args.user is not None else None,
            client_id=args.client_id,
            client_secret=args.client_secret,
            verify_ssl=not args.skip_ssl,
            init_doppler=True,
        )

        space = Space(
            cc,
            org_name=args.org,
            space_name=args.space,
            is_debug=True
        )

        dumps_kwargs = {}
        if args.pretty_print:
            dumps_kwargs['indent'] = 4

        if args.url:
            req = space.request(args.url)
            if not args.list_all:
                return print(req.get().text)
            else:
                res = cc.get_all_resources(req)
        elif args.show_org:
            res = space.org
        else:
            res = space.space

        return print(json.dumps(res, **dumps_kwargs))

    main()
