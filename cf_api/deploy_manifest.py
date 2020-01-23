from __future__ import print_function
import argparse
import fnmatch
import hashlib
import json
import os
import random
import re
import string
import zipfile
import sys
import time
import yaml
import logging
import signal
import traceback
from getpass import getpass
from uuid import uuid4
import cf_api
from . import logs_util
from . import routes_util
from . import dropsonde_util
from . import exceptions as exc

manifest_map = {
    'health_check_timeout': 'timeout',
    'health_check_type': 'health-check-type',
    'no_hostname': 'no-hostname',
    'random_route': 'random-route',
    'no_route': 'no-route',
    'docker_image': 'docker',
}


logger = logging.getLogger('cf_api.deploy_manifest')
logger.setLevel(logging.DEBUG)
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
ch = logging.StreamHandler()
ch.setFormatter(formatter)
logger.addHandler(ch)


class Deploy(object):
    """This class is able to deploy or destroy applications from Cloud Foundry
    Application Manifest files. Only part of the manifest spec is supported at
    this time. See
    https://docs.cloudfoundry.org/devguide/deploy-apps/manifest.html
    for available manifest parameters and further documentation.

    Supported manifest attributes include the following::

        name
        random-route
        buildpack
        stack
        command
        host
        hosts
        routes
          route
        instances
        memory
        disk
        no-route
        no-hostname
        timeout
        health-check-type
        env
        services
        docker-image
          uri
          username
          password OR envvar:CF_DOCKER_PASSWORD

    """

    _manifest_dict = None
    _manifest_filename = None

    _existing_app = None
    _existing_services = None
    _upload_job = None

    _space = None
    _org = None
    _app = None
    _stack = None
    _domain = None
    _service_instances = None
    _domains = None

    _source_dirname = None
    _tailing_thread = None

    is_debug = False

    def __init__(self, cc, manifest_filename, **manifest):
        """Creates a new configuration for deploying or destroying an app.

        Args:
            cc (cf_api.CloudController): authenticated instance of
                CloudController
            manifest_filename (str): the filename of the application manifest
                to be deployed
        """
        self._cc = cc
        self._manifest_filename = manifest_filename
        self._manifest_dict = manifest
        self._service_instances = {}

    def __getattr__(self, item):
        """This is an accessor for manifest dictionary properties
        """
        item = manifest_map.get(item, item)
        value = self._manifest_dict.get(item, None)
        if 'memory' == item:
            value = to_mb(value)
        elif 'disk_quota' == item:
            value = to_mb(value)
        return value

    def clone(self, new_name):
        """Copy this manifest to a new Deploy object with a new app name. All
        manifest attributes will be copied.

        Args:
            new_name (str): name to be replaced into the copied Deploy object

        Returns:
            Deploy
        """
        cl = Deploy(self._cc, self._manifest_filename, **self._manifest_dict)
        cl._manifest_dict['name'] = new_name
        cl._space = self._space
        cl._org = self._org
        cl.is_debug = self.is_debug
        return cl

    def set_org_and_space(self, org_name, space_name):
        """Sets the org / space where this application will be deployed

        Args:
            org_name (str): application's org name
            space_name (str): application's space name

        Returns:
            Deploy: self
        """
        res = self._cc.organizations().get_by_name(org_name)
        self._assert_no_error(res)
        self._org = res.resource

        res = self._cc.request(self._org.spaces_url).get_by_name(space_name)
        self._assert_no_error(res)
        self._space = res.resource

        return self

    def set_org_and_space_dicts(self, org_dict, space_dict):
        """Sets the internal org / space settings using existing resource dicts
        where this application will be deployed. Using this method saves the
        extra requests required to internally fetch the org and space.

        Args:
            org_dict (dict|Resource): application's org dict to be used
                internally
            space_dict (dict|Resource): application's space dict to be used
                internally

        Returns:
            Deploy: self
        """
        self._space = space_dict
        self._org = org_dict
        return self

    def set_source_dirname(self, dirname):
        """Sets the app source directory which will be deployed

        Args:
            dirname (str)

        Returns:
            Deploy: self
        """
        self._source_dirname = dirname
        return self

    def set_debug(self, is_debug):
        """Sets a debug flag indicating whether this deployment will log
        progress messages

        Args:
            is_debug (bool)

        Returns:
            Deploy: self
        """
        self.is_debug = is_debug
        return self

    def log(self, *args, **kwargs):
        """Logs for this class, while respecting the debug flag
        """
        if self.is_debug:
            return log(*args, **kwargs)

    def _assert_org_and_space(self):
        """Asserts that an org / space has been set or throws an error
        """
        if not self._org:
            raise exc.InvalidArgsException(
                'Org is required to get the app', 500)
        if not self._space:
            raise exc.InvalidArgsException(
                'Space is required to get the app', 500)

    def _get_source_dirname(self):
        """Gets the app source dirname that will be archived and uploaded. If
        the manifest `path` attribute specifies a file, and if it's a relative
        path, then the given path will be prepended with
        `dirname(manifest_filename)` and returned. If `path` is not found then
        `dirname(manifest_filename)` will be returned.
        """
        if self._source_dirname:
            return self._source_dirname

        manifest_dirname = os.path.dirname(self._manifest_filename)
        if self.path:
            path = self.path
            if not path.startswith(os.path.sep):
                path = os.path.join(manifest_dirname, path)
            if os.path.isdir(path):
                self._source_dirname = os.path.normpath(path)

        if not self._source_dirname:
            self._source_dirname = manifest_dirname

        if not self._source_dirname.endswith(os.path.sep):
            self._source_dirname += os.path.sep

        return self._source_dirname

    def _get_archive_filename(self):
        """Gets the archive filename that will be uploaded. If the manifest
        `path` attribute specifies a file, that path will be used, and if it's
        a relative path, prepended with `dirname(manifest_filename)`. If
        the manifest `path` attribute is not set, then a randomized filename
        will be returned for later use in zipping the app archive for upload.
        """
        if self._archive_filename:
            return self._archive_filename

        if self.path:
            path = self.path
            if not path.startswith(os.path.sep):
                manifest_dirname = os.path.dirname(self._manifest_filename)
                path = os.path.join(manifest_dirname, path)
            if os.path.isfile(path):
                self._archive_filename = os.path.normpath(path)
                return path

        filename = os.path.basename(self.name) + '-' + str(uuid4()) + '.zip'
        self._archive_filename = \
            os.path.normpath(os.path.join(os.path.sep, 'tmp', filename))
        return self._archive_filename

    def _cleanup_archive(self):
        if not self._archive_filename:
            raise exc.InvalidStateException(
                'Archive has not been created!', 500)
        filename = self._get_archive_filename()
        if os.path.isfile(filename):
            os.unlink(filename)

    # Stacks

    def _get_stack(self):
        """Loads the required stack resource based on the manifest stack
        """
        self.log('get stack', self.stack)
        if self._stack is not None:
            return self._stack
        self._stack = self._cc.stacks().get_by_name(self.stack).resource
        return self._stack

    # Domains

    def _get_primary_domain(self):
        """Loads the primary domain resource
        """
        if self._domain is not None:
            return self._domain
        self._domain = self._cc.shared_domains().get().resource
        return self._domain

    def _get_domain(self, name=None, guid=None):
        if self._domains is None:
            self._domains = {}

        if name in self._domains:
            return self._domains[name]
        else:
            for domain in self._domains.values():
                if domain.guid == guid:
                    return domain

        try:
            domain = self._cc.shared_domains().get_by_name(name).resource
        except exc.ResponseException as e:
            print(str(e))
            domain = None

        if not domain:
            domain = self._cc.request('private_domains')\
                .get_by_name(name).resource

        self._domains[name] = domain
        return domain

    # Apps

    def _get_app(self, use_cache=True):
        """Searches for this deployment's app by name
        """
        self.log('get app', self.name)
        self._assert_org_and_space()
        if self._app is not None and use_cache:
            return self._app
        res = self._cc.request(self._space.apps_url).get_by_name(self.name)
        if res.has_error:
            if 'not found' in res.error_message:
                return None
            else:
                res.raise_error()
        self._app = res.resource
        return res.resource

    # Routes

    def _search_routes(self, routes_url,
                       host=None, domain_guid=None, domain_name=None,
                       port=None, path=None, **kwargs):
        if domain_name is not None and domain_guid is not None:
            raise exc.InvalidArgsException('domain_name and domain_guid may '
                                           'not both be set')
        if domain_guid is None:
            if domain_name is not None:
                domain = self._get_domain(name=domain_name)
            else:
                domain = self._get_primary_domain()
                domain_name = domain.name
            domain_guid = domain.guid

        args = ['domain_guid', domain_guid, 'host', host]
        if port is not None:
            args.extend(['port', port])
        if path is not None:
            args.extend(['path', path])
        self.log('searching routes', format_route(
            host=host,
            domain_name=domain_name,
            port=port,
            path=path,
        ))

        return self._cc.request(routes_url).search(*args).resources

    # Service Instance

    def _get_service_instances(self, name):
        """Finds a service by name within the current space
        """
        if self._service_instances is not None and \
                name in self._service_instances:
            return self._service_instances[name]

        res = self._cc.request(self._space.service_instances_url) \
            .get_by_name(name)
        self._service_instances[name] = res.resource
        return self._service_instances[name]

    # App Operations

    def _create_app_params(self):
        """Assembles a POST body (dict) of values to be sent in creating the
        app based on the app manifest dictionary.
        """
        self._assert_org_and_space()
        self._get_stack()
        params = dict(
            name=self.name,
            space_guid=self._space.guid,
        )
        if self.stack:
            params['stack_guid'] = self._stack.guid
        if self.buildpack:
            params['buildpack'] = self.buildpack
        if self.env:
            params['environment_json'] = self.env
        if self.command:
            params['command'] = self.command
        if self.docker_image:
            username = self.docker_image.get('username')
            password = self.docker_image.get(
                'password', os.getenv('CF_DOCKER_PASSWORD'))
            params['docker_image'] = self.docker_image.get('image')
            params['docker_credentials'] = {
                'username': username,
                'password': password,
            }
        if not self.no_route:
            params['health_check_type'] = self.health_check_type or 'port'
            params['health_check_timeout'] = self.health_check_timeout or 60
        else:
            if self.health_check_type:
                params['health_check_type'] = self.health_check_type
            if self.health_check_timeout:
                params['health_check_timeout'] = self.health_check_timeout

        params['instances'] = self.instances or 2
        params['memory'] = self.memory or 512
        params['disk_quota'] = self.disk_quota or 512

        return params

    def _create_app(self):
        """Creates the app from the manifest params
        """
        self.log('create app', self.name)
        params = self._create_app_params()
        return self._cc.apps().set_params(**params).post().resource

    def _delete_app(self):
        """Deletes the app
        """
        self.log('delete app', self.name)
        app = self._get_app(False)
        res = self._cc.request(app['metadata']['url']).delete()
        return res

    def _update_app(self):
        """Updates the app from the manifest params
        """
        self.log('update app')
        if not self._get_app():
            raise exc.NotFoundException('App not found', 404)
        params = self._create_app_params()
        return self._cc.apps(self._app.guid).set_params(**params).put()

    def _state_app(self, state):
        """Sets the `state` field on the app for `STARTED` or `STOPPED`.
        """
        self.log('set app state', state)
        if not self._get_app():
            raise exc.NotFoundException('App not found', 404)
        res = self._cc.apps(self._app.guid) \
            .set_query(('async', 'true')) \
            .set_params(state=state).put()
        self._assert_no_error(res)
        return res.resource

    def _create_bits_archive(self):
        """Creates an archive file of this app if it's not already specified
        in the manifest
        """
        archive_file = self._get_archive_filename()
        if not os.path.isfile(archive_file):
            source_dir = self._get_source_dirname()
            self.log('zipping archive', source_dir)
            zip_dir(source_dir, archive_file, debug=self.log)
            self.log('created bits archive', archive_file)
        else:
            self.log('found bits archive', archive_file)

    def _upload_bits_archive(self):
        """Uploads the archive file of this app to the Cloud Controller. This
        function uses the `async=true` upload and so this function may be
        called until the job returned initially is complete. When called, this
        function returns True until the job is finished and then returns False.
        """
        if self._upload_job:
            status = self._upload_job['entity']['status']
            if status not in ['finished', 'failed']:
                res = self._cc.request(
                    self._upload_job['metadata']['url']).get()
                self._assert_no_error(res)
                self._upload_job = res.resource
                self.log('upload status', res.resource.status)
                time.sleep(1)
                return True
            elif 'failed' == status:
                raise exc.CFException('Job failed!', 500)
            return False

        archive_filename = self._get_archive_filename()
        self.log('uploading bits archive', archive_filename)
        if not os.path.isfile(archive_filename):
            raise exc.InvalidStateException('Archive file not found', 500)

        resources = []

        # res = self._cc.resource_match()\
        #     .set_params(resources)\
        #     .put()
        # if not res.has_error and len(json.loads(res.text)) > 0:
        #     self.log(res.text)
        #     return False

        with open(archive_filename, 'rb') as f:
            res = self._cc.apps(self._app.guid, 'bits') \
                .set_query(('async', 'true')) \
                .add_field('resources', json.dumps(resources)) \
                .add_file('application', 'application.zip', f,
                          'application/zip') \
                .put()

        self._assert_no_error(res)
        self._upload_job = res.resource

        return True

    # Route Operations

    def _create_routes(self, bind_routes=False, new_app=False):
        """Creates routes for this app based on the manifest params. This
        function will also bind routes to this app if specified.

        The first route will go untouched if there is more than one route
        already attached to the app. Only when there are no routes attached to
        the app, will the `random-route` and `name` or `host` manifest
        attributes be applied.
        """
        self.log('create routes')

        if self.routes and (
                self.host or self.hosts or self.domain or
                self.domains or self.no_hostname):
            raise exc.CFException(
                    'routes attribute is not allowed with'
                    'host, hosts, domain, domains, or no-hostname '
                    'manifest attributes')

        if not self.no_route:

            if not self.routes:
                hosts = []
                if self.hosts:
                    if self.host:
                        hosts.append(self.host)
                    hosts.extend(self.hosts)
                elif self.host:
                    hosts.append(self.host)
                else:
                    routes = self._cc.request(self._app.routes_url)\
                            .get().resources
                    if not routes:
                        host = self.name
                        if self.random_route:
                            host += '-' + rand(8)
                        hosts.append(host)

                for host in hosts:
                    route = self._create_route(host)
                    if bind_routes:
                        self._bind_route(route)

            else:
                for route in self.routes:
                    route = self._create_route_from_entry(route)
                    if bind_routes:
                        self._bind_route(route)

    def _create_route_from_entry(self, route):
        host, domain_name, port, path = routes_util.decompose_route(
                route['route'])
        return self._create_route(
                host,
                domain_name=domain_name, path=path, port=port,
        )

    def _create_route(self, host, domain_name=None, path='', port=None):
        """Creates an individual hostname attached to the domain. If this is
        a primary route (i.e. `name`, `host`) then the `random-route` manifest
        attribute will be applied.
        """
        self.log('creating route', host)

        host = sanitize_domain(host)
        if domain_name is not None:
            domain = self._get_domain(domain_name)
        else:
            domain = self._get_primary_domain()
        domain_guid = domain.guid
        p = dict(
            host=host,
            domain_guid=domain_guid,
            space_guid=self._space.guid
        )
        if path is not None:
            p['path'] = path
        if port is not None:
            p['port'] = port

        routes = self._search_routes(
            self._space.routes_url,
            host=host,
            domain_name=domain_name,
            port=port,
            path=path)
        if routes:
            self.log('route exists, skipping', host)
            return routes[0]

        res = self._cc.routes().set_params(**p).post()
        self._assert_no_error(res)
        return res.resource

    def _bind_route(self, route):
        """Binds a route to the current app.
        host, route_guid, domain_guid=None
        """
        if route is None:
            return

        self.log('binding route', route.host)
        route_guid = route.guid
        search = {'host': route.host,
                  'port': route.port,
                  'path': route.path,
                  'domain_guid': route.domain_guid}

        routes = self._search_routes(self._app.routes_url, **search)
        if routes:
            return

        res = self._cc.request(self._app.routes_url, route_guid).put()
        self._assert_no_error(res)

    def _unbind_routes(self, destroy_routes=True):
        """Unbinds routes from this app. This will also destroy the routes
        if specified.
        """
        app = self._get_app(False)
        res = self._cc.request(app.routes_url).get()
        self._assert_no_error(res)
        responses = []
        for route in res.resources:
            res = self._cc.request(app.routes_url, route.guid).delete()
            self._assert_no_error(res)

            if not destroy_routes:
                responses.append(res)
            else:
                res = self._cc.request(route['metadata']['url']).delete()
                self._assert_no_error(res)
                responses.append(res)
        return responses

    # Service Operations

    def _get_service_binding(self, service_name):
        app = self._get_app()
        service = self._get_service_instances(service_name)
        res = self._cc.request(app.service_bindings_url)\
            .search('service_instance_guid', service.guid)
        self._assert_no_error(res)
        return res.resource

    def _bind_services(self):
        """Binds services specified in the `services` manifest attribute
        to this app
        """
        self.log('bind services')
        if not self.services:
            return []
        return [self._bind_service(service_name)
                for service_name in self.services]

    def _bind_service(self, service_name):
        """Binds an individual app to a service given the service name
        """
        self.log('bind service', service_name)
        service_binding = self._get_service_binding(service_name)
        if service_binding:
            return service_binding
        service_instance = self._get_service_instances(service_name)
        res = self._cc.service_bindings().set_params(
            service_instance_guid=service_instance.guid,
            app_guid=self._app.guid,
        ).post()
        self._assert_no_error(res)
        return res

    def _unbind_services(self):
        """Unbinds services specified in the `services` manifest attribute
        from this app
        """
        self.log('unbind services')
        if not self.services:
            return []
        return [self._unbind_service(service_name)
                for service_name in self.services]

    def _unbind_service(self, service_name):
        """Unbinds an individual service by name from the current app
        """
        self.log('unbind service', service_name)
        app = self._get_app(use_cache=False)
        service_instance = self._get_service_instances(service_name)

        if app.service_bindings_url:
            res = self._cc.request(
                app.service_bindings_url
            ).get_by_name(service_instance.guid, 'service_instance_guid')
            self._assert_no_error(res)
            service_binding = res.resource

            res = self._cc.request(
                app.service_bindings_url, service_binding.guid).delete()
            self._assert_no_error(res)
            return res
        return None

    # Tail App after push

    def _start_tailing_thread(self):

        def render_log(msg):
            try:
                msg = dropsonde_util.DopplerEnvelope.wrap(msg)
                if msg and msg.is_event_type('LogMessage'):
                    self.log(
                        ':'.join(['app', self.name]),
                        '-',
                        dropsonde_util.format_unixnano(msg['timestamp']),
                        msg.message,
                        level=logging.INFO
                    )
            except:
                logger.error(traceback.format_exc())
                self._stop_tailing_thread()

        def sig_handler(sig, frame):
            self._stop_tailing_thread()
            self.log('Ctrl-C pressed. Stopping...')
            sys.exit(1)

        signal.signal(signal.SIGINT, sig_handler)

        if self._tailing_thread is None or self._tailing_thread.is_terminated:
            app = self._get_app()
            self._tailing_thread = logs_util.TailThread(
                self._cc.new_doppler(), app.guid, render_log=render_log)
            self._tailing_thread.start()

    def _stop_tailing_thread(self):
        if self._tailing_thread is not None:
            if not self._tailing_thread.is_terminated:
                self._tailing_thread.terminate()
            else:
                self._tailing_thread = None

    # Wait for App to start after push

    def wait_for_app_start(self, interval=20, timeout=300, tailing=False):
        """This function checks if the app has started on the given interval
        and 1) finishes when the app has started or 2) throws if the timeout
        has passed and the app has not started

        Args:
            interval (int): seconds on which to check if the app has started
            timeout (int): max seconds for which to wait for the app to start
            tailing (bool): if true, this will open a websocket and print out
                the application logs in real-time
        """
        app = self._get_app(use_cache=False)
        if not app:
            return
        if tailing:
            self._start_tailing_thread()
        t = time.time()
        all_running = False
        while 'STAGED' != app['entity']['package_state'] or not all_running:
            app = self._get_app(use_cache=False)
            if 'STAGED' == app['entity']['package_state']:
                res = self._cc.apps(app.guid, 'instances').get()
                all_running = True
                for index, instance in res.data.items():
                    if 'RUNNING' != instance['state']:
                        all_running = False
                        break

            time.sleep(interval)
            if time.time() - t > timeout:
                if tailing:
                    self._stop_tailing_thread()
                raise exc.TimeoutException(
                    'Staging never finished. Timed out after {0} '
                    'seconds'.format(timeout), 500)
        if tailing:
            self._stop_tailing_thread()

    # Stop / Start

    def stop(self):
        """Stop the app

        Returns:
            Deploy: self
        """
        self._state_app('STOPPED')
        return self

    def start(self):
        """Start the app

        Returns:
            Deploy: self
        """
        self._state_app('STARTED')
        return self

    # Push

    def push(self, no_start=False):
        """This command orchestrates the entire deployment of an app, handling
        both create and update scenarios. This command attempts to replicate
        the `cf push` command.

        The flow is roughly as follows::

            Create or update the app parameters
            Bind services to the app
            Archive and upload the app bits
            Create and bind routes to the app
            Restart the app

        Returns:
            None
        """
        self.log('Checking org / space...', level=logging.INFO)
        self._assert_org_and_space()
        self.log('OK', level=logging.INFO)

        self.log('Checking stack...', level=logging.INFO)
        self._get_stack()
        self.log('OK', level=logging.INFO)

        try:
            self._get_app()
        except Exception as e:
            self.log(str(e))

        if not self._app:
            new_app = True
            self.log('Creating app...', level=logging.INFO)
            self._app = self._create_app()
        else:
            new_app = False
            self.log('Updating app...', level=logging.INFO)
            self._update_app()
            self._get_app()
        self.log('OK', level=logging.INFO)

        self.log('Binding services...', level=logging.INFO)
        self._bind_services()
        self.log('OK', level=logging.INFO)

        if not self.docker_image:
            self.log('Creating app bits archive...',
                     level=logging.INFO)
            self._create_bits_archive()
            self.log('OK', level=logging.INFO)

            self.log('Uploading app bits to Cloud Controller...',
                     level=logging.INFO)
            while self._upload_bits_archive():
                pass
            self.log('OK', level=logging.INFO)

            self.log('Clean up app bits archive...', level=logging.INFO)
            self._cleanup_archive()
            self.log('OK', level=logging.INFO)

        if self.no_route:
            self.log('Skipping routes...', level=logging.INFO)
            self._unbind_routes()
        else:
            self.log('Binding routes...', level=logging.INFO)
            self._create_routes(bind_routes=True, new_app=new_app)
        self.log('OK', level=logging.INFO)

        if not no_start:
            self.log('Stopping app...', level=logging.INFO)
            self.stop()
            self.log('OK', level=logging.INFO)

            self.log('Starting app...', level=logging.INFO)
            self.start()
            self.log('OK', level=logging.INFO)

    # Destroy

    def destroy(self, destroy_routes=False):
        """This command orchestrates the entire teardown and cleanup of the
        app's resources. This command attempts to replicate the `cf delete`
        command. This command will optionally destroy any routes associated
        with this app as well.

        The flow is roughly as follows::

            Check if the app exists
            Stop the app
            Unbind services
            Unbind routes (and optionally destroy)
            Delete the app

        Args:
            destroy_routes (bool): if true, this will delete all routes
                associated with the application

        Returns:
            None
        """
        self._assert_org_and_space()
        try:
            self.log('Checking if app exists...', level=logging.INFO)
            self._get_app(use_cache=False)
            self.log('OK', level=logging.INFO)
        except Exception as e:
            self.log(str(e))
            return

        self.log('Stopping app...', level=logging.INFO)
        self._state_app('STOPPED')
        self.log('OK', level=logging.INFO)

        self.log('Unbinding services...', level=logging.INFO)
        self._unbind_services()
        self.log('OK', level=logging.INFO)

        self.log('Unbinding routes...', level=logging.INFO)
        self._unbind_routes(destroy_routes)
        self.log('OK', level=logging.INFO)

        self.log('Deleting app...', level=logging.INFO)
        self._delete_app()
        self.log('Deleted app', level=logging.INFO)

    @staticmethod
    def _assert_no_error(res):
        if res.has_error:
            res.raise_error()

    @staticmethod
    def parse_manifest(manifest_filename, cloud_controller):
        """This function parses an application manifest and creates a list
        of deploy instances to orchestrate push/destroying the app. This
        function will also handle the merging of top level attributes
        onto individual app declarations as well.

        Args:
            manifest_filename (str): filename to the application manifest
            cloud_controller: an initialized instance of cf_api.CloudController

        Returns:
            list[Deploy]: a list of application manifest objects that can be
                          pushed
        """
        if not os.path.isfile(manifest_filename):
            raise exc.InvalidStateException(
                'File does not exist: {0}'
                .format(manifest_filename), 500)

        with open(manifest_filename, 'r') as f:
            manifest_dict = yaml.load(f)

        if 'applications' not in manifest_dict:
            _manifest_dict = dict(applications=[manifest_dict])
            manifest_dict = _manifest_dict

        pushes = []
        for app in manifest_dict['applications']:
            Deploy._merge_app_manifest(manifest_dict, app)
            push = Deploy(cloud_controller, manifest_filename, **app)
            pushes.append(push)

        return pushes

    @staticmethod
    def _merge_app_manifest(manifest_dict, app_dict, defaults_dict=None):
        """This function merges the global dict with the app dict giving
        app specified parameters priority.
        """
        no_merge_keys = ['applications']
        if defaults_dict is None:
            defaults_dict = {}
        for name, value in manifest_dict.items():
            if name not in no_merge_keys:
                value = app_dict.get(name, value)
                app_dict[name] = value
        for name, value in defaults_dict.items():
            if name not in no_merge_keys:
                value = defaults_dict.get(name, value)
                app_dict[name] = value

    @staticmethod
    def wait_for_apps_start(deploys, interval=20, timeout=300, tailing=False):
        """This function waits for the apps to be staged with all instances
        running. It will check every interval and time out if it all instances
        are not up within the timeout.

        Args:
            deploys list[Deploy]: accepts a list of initialized manifest
                objects
            interval (int): seconds on which to check if the apps are started
            timeout (int): seconds to wait for the apps to start
            tailing (bool): if true, this will open a websocket and print out
                the application logs in real-time
        """
        if tailing:
            for app in deploys:
                app._start_tailing_thread()
        todo = {app.name: app for app in deploys}
        t = time.time()
        while len(todo) > 0:
            for app in [v for v in todo.values()]:
                app.log('checking if ', app.name, 'is up...')
                app_ = app._get_app(use_cache=False)
                if not app_:
                    raise exc.NotFoundException('App {0} not found'
                                                .format(app.name), 404)
                if 'STAGED' == app_['entity']['package_state']:
                    res = app._cc.apps(app_.guid, 'instances').get()
                    all_running = True
                    for index, instance in res.data.items():
                        if 'RUNNING' != instance['state']:
                            all_running = False
                            break
                    if all_running:
                        if tailing:
                            todo[app.name]._stop_tailing_thread()
                        del todo[app.name]

            if len(todo) == 0:
                break

            time.sleep(interval)
            if time.time() - t > timeout:
                raise exc.TimeoutException(
                    'Staging never finished. Timed out after {0} '
                    'seconds'.format(timeout), 500)
        log('All apps started successfully.', level=logging.INFO)


def parse_ignore_file(ignorefile, include_star=True):
    """Parses a .gitignore or .cfignore file for fnmatch patterns
    """
    try:
        with open(ignorefile, 'r') as f:
            _cfignore = f.read().split('\n')

        cfignore = []
        for l in _cfignore:
            if l and not l.startswith('#'):
                l = re.sub('\s*#.*', '', l).strip()
                if include_star and l.endswith('/'):
                    l += '*'
                cfignore.append(l)
    except Exception as e:
        log(e)
        cfignore = []

    cfignore.extend(['.git/', '.gitignore', '.cfignore', 'manifest.yml'])

    return cfignore


def list_files(source_directory, fnmatch_list=None):
    """Lists files in the given directory and excludes files or directories
    that match any pattern in the fnmatch_list.
    """
    if not fnmatch_list:
        cfignore_filename = os.path.join(source_directory, '.cfignore')
        fnmatch_list = parse_ignore_file(cfignore_filename, include_star=False)
    files = os.walk(source_directory)
    _files = []
    for tup in files:
        dirname = tup[0]
        subdirs = tup[1]
        filenames = tup[2]
        for d in subdirs:
            d = os.path.join(dirname, d)
            if not d.endswith('/'):
                d += '/'
            _files.append(d)

        for f in filenames:
            f = os.path.join(dirname, f)
            _files.append(f)

    if not source_directory.endswith('/'):
        source_directory += '/'

    files = []
    for f in _files:
        f = f.replace(source_directory, '')
        matches = True
        for pat in fnmatch_list:
            if fnmatch.fnmatch(f, pat) or f.startswith(pat):
                matches = False
                break
        if matches:
            files.append(dict(
                fn=f,
                sha1=file_sha1(f),
                size=file_size(f),
            ))

    return files


def zip_dir(source_dir, archive_name, ignorefile=None, debug=None):
    """Creates an archive of the given directory and stores it in the given
    archive_name which may be a filename as well. By default, this function
    will look for a .cfignore file and exclude any matching entries from the
    archive.
    """
    archive_name = archive_name or (os.path.basename(source_dir) + '.zip')
    if not ignorefile:
        ignorefile = os.path.join(source_dir, '.cfignore')
    ignore_files = parse_ignore_file(ignorefile, include_star=False)

    if archive_name.startswith('/'):
        archive_file = archive_name
    else:
        archive_file = os.path.join(os.path.dirname(source_dir), archive_name)

    if not source_dir.endswith('/'):
        source_dir += '/'

    os.chdir(source_dir)
    files = list_files(source_dir, ignore_files)
    with zipfile.ZipFile(
            archive_file,
            mode='w',
            compression=zipfile.ZIP_DEFLATED) as zipf:
        for f in files:
            name = f['fn'].replace(source_dir, '')
            if debug:
                if not callable(debug):
                    debug = log
                debug('    adding:', name)
            compress = zipfile.ZIP_STORED if f['fn'].endswith(
                '/') else zipfile.ZIP_DEFLATED
            zipf.write(f['fn'], arcname=name, compress_type=compress)

    return archive_file


def file_sha1(filename):
    """Creates a SHA1 of the given file. This is useful in resource matching
    for uploading app bits.
    """
    if os.path.isdir(filename):
        return '0'
    with open(filename, 'rb') as f:
        return hashlib.sha1(f.read()).hexdigest()


def file_size(filename):
    """Get the size of the given file. This is useful in resource matching
    for uploading app bits.
    """
    if os.path.isdir(filename):
        return 0
    return os.path.getsize(filename)


def to_mb(s):
    """Simple function to convert `disk_quota` or `memory` attribute string
    values into MB integer values.
    """
    if s is None:
        return s
    if s.endswith('M'):
        return int(re.sub('M$', '', s))
    elif s.endswith('G'):
        return int(re.sub('G$', '', s)) * 1000
    return 512


def log(*args, **kwargs):
    logger.log(kwargs.get('level', logging.DEBUG), ' '.join([str(a)
                                                             for a in args]))
#    sys.stdout.write(' '.join([str(a) for a in args]) + '\n')
#    sys.stdout.flush()


def format_route(**route):
    uri = route['host']
    if 'domain_name' in route and route['domain_name']:
        uri = '.'.join([uri, str(route['domain_name'])])
    if 'port' in route and route['port']:
        uri = ':'.join([uri, str(route['port'])])
    if 'path' in route and route['path']:
        sep = '' if route['path'].startswith('/') else '/'
        uri = sep.join([uri, str(route['path'])])
    return uri


def rand(n):
    rand_chars = ''.join([string.digits, string.ascii_lowercase])
    return ''.join(random.sample(rand_chars, n))


def sanitize_domain(host):
    return re.sub('[^a-z0-9.-]+', '-', host.lower(), flags=re.I)


if '__main__' == __name__:
    def main():
        """
        This __main__ script replicates the functionality of `cf push` as a
         demonstration of how this library may be used to deploy applications
         to Cloud Foundry directly from Python scripts.

        To run:

            cd path/to/your/app
            python path/to/deploy_manifest.py \
                -v \
                --cloud-controller https://api.your-cf.com \
                -u youser \
                -o yourorg \
                -s yourspace \
                -m path/to/your/app/manifest.yml
        """
        args = argparse.ArgumentParser(
                description='This tool deploys an application to Cloud Foundry'
                            ' using an application manifest in the same '
                            'manner as `cf push\'')
        args.add_argument(
            '--cloud-controller', dest='cloud_controller', required=True,
            help='The Cloud Controller API endpoint (excluding leading'
                 ' slashes)')
        args.add_argument(
            '-u', '--user', dest='user', default=None,
            help='The user to use for the deployment')
        args.add_argument(
            '-o', '--org', dest='org', required=True,
            help='The organization to which the app will be deployed')
        args.add_argument(
            '-s', '--space', dest='space', required=True,
            help='The space to which the app will be deployed')
        args.add_argument(
            '-m', '--manifest', dest='manifest_filename', default='',
            help='The path to the application manifest to be deployed')
        args.add_argument(
            '-v', '--verbose', dest='verbose', action='store_true',
            help='Indicates that verbose logging will be enabled')
        args.add_argument(
            '-w', '--wait', dest='wait', action='store_true',
            help='Indicates to wait until the application starts before '
                 'exiting')
        args.add_argument(
            '-l', '--log-level', dest='log_level', default='DEBUG',
            type=lambda l: l.upper(),
            help='Sets the log verbosity')
        args.add_argument(
            '--skip-ssl', dest='skip_ssl', action='store_true',
            help='Indicates to skip SSL cert verification')
        args.add_argument(
            '--destroy', dest='destroy', action='store_true',
            help='Indicates to destroy the app defined in the manifest file. '
                 'The user will be asked to confirm before destroying is '
                 'executed')
        args.add_argument(
            '--destroy-routes', dest='destroy_routes', action='store_true',
            help='To be used with --destroy. Indicates to destroy the '
                 'application\'s routes in addition to the app itself')
        args.add_argument(
            '--client-id', dest='client_id', default='cf',
            help='Used to set a custom deployment client ID')
        args.add_argument(
            '--client-secret', dest='client_secret', default='',
            help='Secret corresponding to --client-id')
        args = args.parse_args()

        if not hasattr(logging, args.log_level):
            raise exc.CFException(
                'Log level {0} not found'.format(args.log_level), 400)
        else:
            logger.setLevel(getattr(logging, args.log_level))

        if args.user:
            username = args.user
            password = getpass().strip()
            refresh_token = None
        else:
            username = None
            password = None
            refresh_token = os.getenv('CF_REFRESH_TOKEN')

        logger.info('Authenticating...')
        cc = cf_api.new_cloud_controller(
            args.cloud_controller,
            username=username,
            password=password,
            refresh_token=refresh_token,
            client_id=args.client_id,
            client_secret=args.client_secret,
            verify_ssl=not args.skip_ssl
        )
        logger.info('OK')

        proj_dir = os.getcwd()
        manifest_filename = args.manifest_filename
        if not manifest_filename:
            manifest_filename = os.path.join(proj_dir, 'manifest.yml')
        elif not manifest_filename.startswith('/'):
            manifest_filename = os.path.join(proj_dir, manifest_filename)

        ms = Deploy.parse_manifest(manifest_filename, cc)

        for m in ms:
            m.set_debug(args.verbose)
            m.set_org_and_space(args.org, args.space)

            if args.destroy:
                if six.input('Destroying app {0}. Are you sure? (y/n) '
                             .format(m.name)) == 'y':
                    m.destroy(args.destroy_routes)
                else:
                    log('Skipping destroying app {0}...'.format(m.name))
            else:
                m.push()

        if args.wait:
            Deploy.wait_for_apps_start(ms, tailing=args.verbose)

    main()
