from __future__ import print_function
import os
import sys
import time
import cf_api
import argparse
from getpass import getpass
from . import exceptions as exc


class DeployService(object):
    """This class provides a basic interface to create and destroy services.
    Note you MUST set a space in which to operate before you can do anything
    with an instance of this class. See `set_org_and_space()` or
    `set_space_guid()` for more info on setting the space.
    """

    _debug = False

    _org = None
    _space = None

    _service = None
    _service_plan = None

    _service_instance = None

    def __init__(self, cc):
        """Initializes a service deployment object

        Args:
             cc (cf_api.CloudController): an initialized instance of
                 CloudController client
        """
        self._cc = cc
        self._service_plan = {}

    def set_org_and_space(self, org_name, space_name):
        """Sets the org and space to be used in this service deployment

        Args:
            org_name (str): name of the organization
            space_name (str): name of the space

        Returns:
            DeployService: self
        """
        res = self._cc.organizations().get_by_name(org_name)
        self._org = res.resource

        res = self._cc.request(self._org.spaces_url).get_by_name(space_name)
        self._space = res.resource
        return self

    def set_space_guid(self, space_guid):
        """Sets the guid of the space to be used in this deployment

        Args:
            space_guid (str): guid of the space

        Returns:
            DeployService: self
        """
        res = self._cc.spaces(space_guid).get()
        self._space = res.resource

        res = self._cc.request(self._space.organization_url).get()
        self._org = res.resource
        return self

    def set_org_and_space_dicts(self, org_dict, space_dict):
        """Sets the internal org / space settings using existing resource dicts
        where this service will be deployed.

        Args:
            org_dict (dict|Resource): service instance's org dict to be used
                internally
            space_dict (dict|Resource): service instance's space dict to be
                used internally

        Returns:
            DeployService: self
        """
        self._space = space_dict
        self._org = org_dict
        return self

    def set_debug(self, debug):
        """Sets a debug flag on whether this client should print debug messages

        Args:
            debug (bool)

        Returns:
            DeployService: self
        """
        self._debug = debug
        return self

    def log(self, *args):
        if self._debug:
            sys.stdout.write(' '.join([str(a) for a in args]) + '\n')
            sys.stdout.flush()

    def _get_service_instance(self, name, no_cache=False):
        """Fetches the service instance object based on the given name. This
        method caches the service instance object by default; set no_cache=True
        in order to fetch a fresh service instance object.

        Args:
            name (str): user defined name of the service instance

        Keyword Args:
            no_cache (bool): skip the cache and re-fetch the service instance

        Returns:
            service_instance (cf_api.Resource): the service object
        """
        self._assert_space()

        if self._service_instance and not no_cache:
            return self._service_instance
        res = self._cc.request(self._space.service_instances_url)\
            .get_by_name(name)
        self._service_instance = res.resource
        return self._service_instance

    def _get_service(self, service_name):
        """Fetches the service provider details by its name

        Args:
            service_name (str): service type name as seen in marketplace

        Returns:
            cf_api.Resource: the service provider object
        """
        if self._service:
            return self._service
        res = self._cc.services().get_by_name(service_name, name='label')
        self._service = res.resource
        return self._service

    def _get_service_plan(self, service_name, service_plan_name):
        """Fetches a service plan's details

        Args:
            service_name (str): service type name as seen in marketplace
            service_plan_name (str): service plan name within the given service

        Returns:
            service_plan (cf_api.Resource): the service plan object
        """
        self._assert_space()
        key = ' / '.join([service_name, service_plan_name])
        if key in self._service_plan:
            return self._service_plan[key]
        self._get_service(service_name)
        service_plan_url = self._service['entity']['service_plans_url']
        res = self._cc.request(service_plan_url).get()
        for plan in res.resources:
            if service_plan_name == plan['entity']['name']:
                self._service_plan[key] = plan
                break
        return self._service_plan[key]

    def _get_last_operation(self, name):
        """Looks up the last operation state for the service.

        Args:
            name (str): the name of the service to be checked

        Returns:
            str: `state` string from the `last_operation` details
        """
        self._get_service_instance(name, no_cache=True)
        lo = self._service_instance['entity']['last_operation']
        return lo['state']

    def _assert_space(self):
        if not self._space:
            raise exc.InvalidStateException('Space is required', 500)

    def create(self, name, service_name, service_plan_name,
               tags=None, parameters=None):
        """Creates a service with the user defined name (name),
        service type (service_name), and service plan name (service_plan_name).

        Args:
            name (str): user defined service name
            service_name (str): type of service to be created
            service_plan_name (str): plan of the service to be create

        Returns:
            cf_api.Resource: the created or existing service object
        """
        self._assert_space()

        service_instance = self._get_service_instance(name)
        if service_instance:
            return service_instance

        service_plan = self._get_service_plan(service_name, service_plan_name)

        if not service_plan:
            raise exc.NotFoundException('Service plan not found', 404)

        body = dict(
            name=name,
            service_plan_guid=service_plan.guid,
            space_guid=self._space.guid
        )
        if tags is not None:
            body['tags'] = tags
        if parameters is not None:
            body['parameters'] = parameters

        res = self._cc.service_instances() \
            .set_query(accepts_incomplete='true') \
            .set_params(**body).post()
        return res.resource

    def destroy(self, name):
        """Destroys a service with the user defined name

        Args:
            name (str): user defined name of the service

        Returns:
             cf_api.Resource: deleted service instance
        """
        self._assert_space()

        service_instance = self._get_service_instance(name)
        if service_instance:
            lastop = service_instance.last_operation
            if 'delete' == lastop['type']:
                return service_instance
            return self._cc \
                .service_instances(service_instance.guid) \
                .set_query(accepts_incomplete='true') \
                .delete()
        return None

    def is_provisioned(self, name):
        """Checks if the service is provisioned

        Args:
            name (str): user defined name of the service

        Returns:
            bool
        """
        self._assert_space()

        return self._get_last_operation(name) == 'succeeded'

    def is_deprovisioned(self, name):
        """Checks if the service is de-provisioned

        Args:
            name (str): user defined name of the service

        Returns:
            bool
        """
        self._assert_space()

        try:
            return not self._get_service_instance(name, no_cache=True)
        except Exception as e:
            print(str(e))
            return True

    def is_provision_state(self, name, state):
        """Checks if the service with `name` is in the given `state`

        Args:
            name (str): user defined service name
            state (str): allowed values are `provisioned` or `deprovisioned`

        Returns:
            bool
        """
        self._assert_space()

        if state not in ['provisioned', 'deprovisioned']:
            raise exc.InvalidArgsException(
                'Invalid service state {0}'.format(state), 500)

        res = self._cc.uaa.refresh_token()
        self._cc.update_tokens(res)

        if 'provisioned' == state:
            return self.is_provisioned(name)
        elif 'deprovisioned' == state:
            return self.is_deprovisioned(name)
        else:
            return False

    def wait_service(self, name, state, timeout=300, interval=30):
        """Waits for the service with `name` to enter the `state` within the
        given `timeout`, while checking on the `interval`. This method WILL
        block until it's the service is in the desired state, or the timeout
        has passed.

        Args:
            name (str): user defined service name
            state (str): allowed values are `provisioned` or `deprovisioned`
            timeout (int=300): units in seconds
            interval (int=30): units in seconds
        """
        self._assert_space()

        t = int(time.time())
        while True:
            if self.is_provision_state(name, state):
                return
            elif 'deprovisioned' == state and self.is_provisioned(name):
                raise exc.InvalidStateException(
                    'Service {0} does not appear to be deprovisioning.'
                    .format(name), 500)
            elif 'provisioned' == state and self.is_deprovisioned(name):
                raise exc.InvalidStateException(
                    'Service {0} does not appear to be provisioning.'
                    .format(name), 500)

            if int(time.time()) - t > timeout:
                raise exc.TimeoutException(
                    'Service {0} provisioning timed out'.format(name), 500)

            lo = self._service_instance['entity']['last_operation']
            self.log(
                'waiting for service', self._org.name, '/', self._space.name,
                self._service_instance.name, lo['type'], lo['state'],
                lo['description'])

            time.sleep(interval)


if '__main__' == __name__:

    def get_status(args):
        if args.provisioned:
            status = 'provisioned'
        elif args.deprovisioned:
            status = 'deprovisioned'
        else:
            status = None
        if 'create' == args.action:
            status = 'provisioned'
        elif 'destroy' == args.action:
            status = 'deprovisioned'
        return status

    def main():
        args = argparse.ArgumentParser(
                description='This tool deploys a service to a Cloud Foundry '
                            'org/space in the same manner as '
                            '`cf create-service\'')
        args.add_argument(
            '--cloud-controller', dest='cloud_controller', required=True,
            help='The Cloud Controller API endpoint '
                 '(excluding leading slashes)')
        args.add_argument(
            '-u', '--user', dest='user',
            help='The user to use for the deployment')
        args.add_argument(
            '-o', '--org', dest='org', required=True,
            help='The organization to which the service will be deployed')
        args.add_argument(
            '-s', '--space', dest='space', required=True,
            help='The space to which the service will be deployed')
        args.add_argument(
            '--skip-ssl', dest='skip_ssl', action='store_true',
            help='Indicates to skip SSL cert verification')
        args.add_argument(
            '--name', dest='name', required=True,
            help='User defined service name to be deployed')
        args.add_argument(
            '--service-name', dest='service_name', required=True,
            help='Service type to be deployed')
        args.add_argument(
            '--service-plan', dest='service_plan', required=True,
            help='Service plan to be deployed')
        args.add_argument(
            '-a', '--action', dest='action', choices=['create', 'destroy'],
            help='Service action to be executed. Only `create\' and '
                 '`destroy\' are supported values')
        args.add_argument(
            '-w', '--wait', dest='wait', default=False, action='store_true',
            help='Indicates to wait until the service is '
                 'created before exiting')
        args.add_argument(
            '-v', '--verbose', dest='verbose',
            default=False, action='store_true',
            help='Indicates that verbose logging will be enabled')
        args.add_argument(
            '--provisioned', dest='provisioned',
            default=False, action='store_true',
            help='Used with --wait. Indicates to wait until the service '
                 'is provisioned')
        args.add_argument(
            '--deprovisioned', dest='deprovisioned',
            default=False, action='store_true',
            help='Used with --wait. Indicates to wait until the service '
                 'is provisioned')
        args.add_argument(
            '-t', '--timeout', dest='timeout',
            type=int, default=300,
            help='Sets a number of seconds to allow before timing out '
                 'the deployment execution')
        args = args.parse_args()

        if args.user:
            username = args.user
            password = getpass('Password: ').strip()
            refresh_token = None
        else:
            username = None
            password = None
            refresh_token = os.getenv('CF_REFRESH_TOKEN')

        cc = cf_api.new_cloud_controller(
            args.cloud_controller,
            username=username,
            password=password,
            refresh_token=refresh_token,
            client_id='cf',
            client_secret='',
            verify_ssl=not args.skip_ssl,
        )

        service_name = args.name
        service = DeployService(cc)\
            .set_debug(args.verbose)\
            .set_org_and_space(args.org, args.space)

        res = None
        status = get_status(args)
        if 'create' == args.action:
            res = service.create(
                service_name,
                args.service_name,
                args.service_plan
            )

        elif 'destroy' == args.action:
            try:
                res = service.destroy(
                    service_name
                )
            except Exception as e:
                service.log(str(e))
                return

        if res is not None:
            service.log(res)

        if status is not None and args.wait:
            service.wait_service(service_name, status, args.timeout)

    main()
