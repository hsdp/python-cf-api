from __future__ import print_function
from six import string_types
import os
import re
import time
import traceback
from . import exceptions as exc
from requests_factory import Request
from requests_factory import Response
from requests_factory import RequestFactory
from requests_factory import WebSocket

if 'true' == os.getenv('CF_API_DEBUG', ''):
    import sys
    sys.path.insert(0, os.getcwd())

try:
    from urllib.parse import urlparse
    from urllib.parse import urlencode
    from urllib.parse import parse_qs
except ImportError:
    from urlparse import urlparse
    from urllib import urlencode
    from urlparse import parse_qs

try:
    import jwt
    from jwt.contrib.algorithms.pycrypto import RSAAlgorithm
    jwt.register_algorithm('RS256', RSAAlgorithm(RSAAlgorithm.SHA256))
except ValueError as e:
    if str(e) != 'Algorithm already has a handler.':
        print(traceback.format_exc())
        raise e


def _print_deprecated_message(from_name, to_name):
    print('{0} is deprecated. Please migrate to {1}'
          .format(from_name, to_name))


def _get_default_var(val, env):
    return os.getenv(env) if val is None else val


class CloudControllerRequest(Request):
    """Encapsulates a request to the Cloud Controller API
    """

    def __init__(self, factory=None):
        super(CloudControllerRequest, self).__init__(factory)

        def response_class(r):
            return CloudControllerResponse(r).set_factory(factory)

        self.set_response_class(response_class)

    def get_by_name(self, value, name='name'):
        """Executes the list entities function searching for the given name

        Returns:
            CloudControllerResponse
        """
        return self.search(name, value)

    def search(self, *qlist, **qdict):
        """Sets the ``q`` query parameter used in listing most entities and
        executes the request

        Args:
            *qlist (tuple[str]): every 2 strings will be joined with a ':' as
                per the search format and each set to a ``q`` param. If only 1
                string is passed, it will be assumed to contain a ':' and will
                be set in the ``q`` param directly.
            **qdict (dict): sets any additional query parameters

        Returns:
            CloudControllerResponse
        """
        if len(qlist) == 0 and len(qdict) == 0:
            raise exc.InvalidArgsException('No search query was given', 500)

        if len(qlist) == 1:
            return self.set_query(q=qlist[0], **qdict).get()
        else:
            qlist = [str(s) for s in qlist]
            qlist = [('q', ':'.join(qlist[i:i+2]))
                     for i in range(0, len(qlist), 2)]
            return self.set_query(*qlist, **qdict).get()


class CloudControllerResponse(Response):
    """Encapsulates a response from the Cloud Controller API
    """
    _factory = None
    _resource_class = None

    def set_factory(self, factory):
        self._factory = factory
        self._resource_class = Resource
        return self

    def set_resource_class(self, resource_class):
        self._resource_class = resource_class
        return self

    @property
    def next_url(self):
        return self.data.get('next_url', None)

    @property
    def error_message(self):
        """Extracts the error message from this response
        """
        if not self.has_error:
            return None

        if isinstance(self._response_parsed, dict) and \
                'error_description' in self._response_parsed:
            return self._response_parsed['error_description']
        return self._response_text

    @property
    def error_code(self):
        """Extracts the error code from this response
        """
        if not self.has_error:
            return None

        if isinstance(self._response_parsed, dict) and \
                'error_code' in self._response_parsed:
            return self._response_parsed['error_code']
        return self._response_text

    @property
    def resources(self):
        """Attempts to parse the response as a resource list

        Returns:
            list[Resource]
        """
        return [self._resource_class(r).set_factory(self._factory) for r in
                self.data['resources']]

    @property
    def resource(self):
        """If the response is an array this gets the first item resource, else
        return the raw response

        Returns:
            Resource
        """
        if 'resources' in self.data:
            if len(self.data['resources']) == 0:
                return None
            else:
                return self._resource_class(self.data['resources'][0]) \
                    .set_factory(self._factory)
        else:
            return self._resource_class(self.data).set_factory(self._factory)


class Resource(dict):
    """Provides shortcuts to the most commonly used fields of Cloud Controller
    resource objects.
    """
    _factory = None

    def __init__(self, response, factory=None):
        super(Resource, self).__init__()
        self._factory = factory
        for n, v in response.items():
            self[n] = v

    def set_factory(self, factory):
        self._factory = factory
        return self

    def __getattr__(self, item):
        return self['entity'].get(item, None)

    @property
    def guid(self):
        """Shortcut to ``metadata.guid``
        """
        return self['metadata']['guid']

    @property
    def name(self):
        """Shortcut to ``entity.name``
        """
        return self['entity']['name']

    @property
    def state(self):
        return self['entity']['state']

    @property
    def status(self):
        return self['entity']['status']

    @property
    def label(self):
        return self['entity']['label']

    @property
    def space_guid(self):
        """Shortcut to ``entity.space_guid``
        """
        return self['entity']['space_guid']

    @property
    def org_guid(self):
        """Shortcut to ``entity.organization_guid``
        """
        return self['entity']['organization_guid']

    @property
    def service_plan_guid(self):
        return self['entity']['service_plan_guid']

    @property
    def spaces_url(self):
        """Shortcut to ``entity.spaces_url``
        """
        return self['entity']['spaces_url']

    @property
    def routes_url(self):
        """Shortcut to ``entity.routes_url``
        """
        return self['entity']['routes_url']

    @property
    def stack_url(self):
        return self['entity']['stack_url']

    @property
    def service_bindings_url(self):
        return self['entity']['service_bindings_url']

    @property
    def apps_url(self):
        return self['entity']['apps_url']

    @property
    def service_instances_url(self):
        return self['entity']['service_instances_url']

    @property
    def organization_url(self):
        """Shortcut to ``entity.organization_url``
        """
        return self['entity']['organization_url']

    def space(self):
        return self._factory.request(self.space_url).get()

    def apps(self):
        return self._factory.request(self.apps_url).get()

    def spaces(self):
        return self._factory.request(self.spaces_url).get()

    def routes(self):
        return self._factory.request(self.routes_url).get()

    def orgs(self):
        return self._factory.request(self.organization_url).get()

    def service_instances(self):
        return self._factory.request(self.service_instances_url).get()


class V3CloudControllerRequest(Request):
    """Encapsulates a request to the Cloud Controller API version 3
    """

    def __init__(self, factory=None):
        super(V3CloudControllerRequest, self).__init__(factory)

        def response_class(r):
            return V3CloudControllerResponse(r).set_factory(factory)

        self.set_response_class(response_class)


class V3CloudControllerResponse(Response):
    """Encapsulates a response from the Cloud Controller API version 3
    """
    _factory = None
    _resource_class = None

    def set_factory(self, factory):
        self._factory = factory
        self._resource_class = V3Resource
        return self

    def set_resource_class(self, resource_class):
        self._resource_class = resource_class
        return self

    @property
    def next_url(self):
        if 'pagination' in self.data and \
                'next' in self.data['pagination'] and \
                self.data['pagination']['next'] is not None and \
                'href' in self.data['pagination']['next']:
            return self.data['pagination']['next']['href']
        return None

    @property
    def error_message(self):
        """Extracts the error message from this response
        """
        if not self.has_error:
            return None

        if isinstance(self._response_parsed, dict) and \
                self._response_parsed.get('errors'):
            return [': '.join([err['title'], err['detail']])
                    for err in self._response_parsed['errors']]
        return [self._response_text.decode('utf-8')]

    @property
    def error_code(self):
        """Extracts the error code from this response
        """
        if not self.has_error:
            return None

        if isinstance(self._response_parsed, dict) and \
                self._response_parsed.get('errors'):
            return [str(err['code'])
                    for err in self._response_parsed['errors']]
        return [self._response_text.decode('utf-8')]

    @property
    def resources(self):
        """Attempts to parse the response as a resource list

        Returns:
            list[Resource]
        """
        return [self._resource_class(r).set_factory(self._factory) for r in
                self.data['resources']]

    @property
    def resource(self):
        """If the response is an array this gets the first item resource, else
        return the raw response

        Returns:
            Resource
        """
        if 'resources' in self.data:
            if len(self.data['resources']) == 0:
                return None
            else:
                return self._resource_class(self.data['resources'][0]) \
                    .set_factory(self._factory)
        else:
            return self._resource_class(self.data).set_factory(self._factory)


class V3Resource(dict):
    """Provides shortcuts to the most commonly used fields of Cloud Controller
    API version 3 resource objects.
    """
    _factory = None

    def __init__(self, response, factory=None):
        super(V3Resource, self).__init__()
        self._factory = factory
        for n, v in response.items():
            self[n] = v

    def set_factory(self, factory):
        self._factory = factory
        return self

    def __getattr__(self, item):
        return self.get(item, None)

    @property
    def guid(self):
        """Shortcut to ``guid``
        """
        return self['guid']

    @property
    def name(self):
        """Shortcut to ``name``
        """
        return self['name']

    @property
    def state(self):
        """Shortcut to ``state``
        """
        return self['state']

    @property
    def space_guid(self):
        """Shortcut to ``relationships.space.data.guid``
        """
        try:
            return self['relationships']['space']['data']['guid']
        except KeyError:
            return None

    @property
    def org_guid(self):
        """Shortcut to ``relationships.organization.data.guid``
        """
        try:
            return self['relationships']['organization']['data']['guid']
        except KeyError:
            return None

    @property
    def href(self):
        """Shortcut to ``links.self.href``
        """
        try:
            return self['links']['self']['href']
        except KeyError:
            return None

    @property
    def organization_url(self):
        """Shortcut to ``links.organization.href``
        """
        try:
            return self['links']['organization']['href']
        except KeyError:
            return None


class CloudController(RequestFactory):
    """Provides base endpoints for building Cloud Controller requests

    Attributes:
        uaa (UAA): UAA instance that was used to authenticate.
        doppler (Doppler): Doppler instance that may be used to access logs.
        ssh_proxy (SSHProxy): SSH Proxy instance that may be used to access
            an app instance shell.
        version (int): Cloud Controller API version to be used when making
            requests
        info (CFInfo): CFInfo instance containing CF service entries for
            various internal services (i.e. Cloud Controller, UAA, Doppler,
            etc.)
    """

    uaa = None
    doppler = None
    ssh_proxy = None
    version = 2
    info = None

    _v3cc = None
    _last_refresh_time = 0

    def __init__(self, base_url):
        """Creates a new instance of the CloudController

        Args:
            base_url (str): The base URL of the Cloud Controller API
        """
        super(CloudController, self).__init__()
        self.set_base_url(base_url)\
            .application_json()\
            .set_request_class(CloudControllerRequest)\
            .set_response_class(CloudControllerResponse)

    @property
    def v3(self):
        if self._v3cc is None:
            self._v3cc = self.new_v3()
        return self._v3cc

    def new_doppler(self):
        """Creates a new, authenticated Doppler instance

        Returns:
            Doppler
        """
        return new_doppler(
            base_url=self.info.doppler_url,
            verify_ssl=self.verify_ssl,
            access_token=self.uaa.get_access_token().to_string()
        )

    def set_info(self, info):
        """Sets the API info object

        Args:
            info (CFInfo): API info data
        """
        self.info = info
        return self

    def set_version(self, version):
        """Sets the API version to be use when creating requests

        Args:
            version (int): API version number
        """
        self.version = version
        return self

    def set_v3(self):
        self.set_version(3)
        self.set_request_class(V3CloudControllerRequest)
        self.set_response_class(V3CloudControllerResponse)
        return self

    def new_v3(self):
        v3cc = self.__class__(self.base_url)
        v3cc.set_v3()
        v3cc.set_uaa(self.uaa)
        v3cc.headers = self.headers
        return v3cc

    def set_uaa(self, uaa):
        """Sets the internal UAA client

        Args:
            uaa (UAA): an initialized instance of UAA class

        Returns:
            self (CloudController)
        """
        self.uaa = uaa
        return self

    def set_doppler(self, doppler):
        """Sets the internal doppler client

        Args:
            doppler (Doppler)

        Returns:
            self (CloudController)
        """
        self.doppler = doppler
        return self

    def set_ssh_proxy(self, ssh_proxy):
        """Sets the internal ssh proxy configuration

        Args:
            ssh (SSHProxy)

        Returns:
            self (CloudController)
        """
        self.ssh_proxy = ssh_proxy
        return self

    def update_tokens(self, res):
        """This method accepts a token response object from the UAA server.
        Note that the ``res.data`` dict must contain at least ``access_token``.

        Args:
            res (CloudControllerResponse)
        """
        if self.uaa:
            self.uaa.update_tokens(res)
        if res.has_error:
            res.raise_error()
        self.set_bearer_auth(res.data['access_token'])

    def refresh_tokens(self, force=False):
        """This method will refresh the internal access token based on the
        expiration time encapsulated in the current token.

        Args:
            force (bool): Default is False. If True, then the tokens will be
                refreshed regardless of whether they've expired
        Returns:
            self (CloudController)
        """
        if not self.uaa:
            raise exc.InvalidStateException(
                'UAA is not initialized. UAA is required to refresh tokens!',
                500)

        if force or self.should_refresh():
            res = self.uaa.refresh_token()
            self.update_tokens(res)
            print('updated tokens')

        return self

    def set_refresh_tokens_callback(self, callback=None):
        """This method sets the internal request callback to refresh the tokens
        when they expire.  This is a convenience method and is not set by
        default.

        Args:
            callback (callable): An optional callback that will be invoked on
                every request to the Cloud Controller and will supply three
                required arguments:
                    req (instanceof Request): the request to be executed
                    cc (CloudController): the cloud controller object
                    did_refresh (bool): whether the tokens were updated

        .. note::

                Note that this callback is called after the tokens are updated
                internally.

        Returns:
            self (CloudController)
        """
        def _refresh_token(req, cc):
            did_refresh = cc.should_refresh()
            cc.refresh_tokens()
            req.set_bearer_auth(cc.uaa.get_access_token().to_string())
            if callable(callback):
                callback(req, cc, did_refresh)

        self.set_callback(_refresh_token, self)
        return self

    def should_refresh(self):
        """Determines whether the internal refresh_interval has passed

        Returns:
            bool
        """
        return self.uaa.get_access_token().is_expired

    def get_all_resources(self, req):
        """Recursively gets all the resources specified by the request. Do not
        execute ``req.get()`` before passing it in. This implementation will
        call ``req.get()`` and continue calling ``next_url`` from the response
        and collect the results until the response has no ``next_url``.

        Args:
            req (Request): a user prepared request that will be used to execute
                and collect all results

        Returns:
            list[Resource]: collected resources in a single list
        """
        res = req.get()
        results = []
        while True:
            results.extend(res.resources)
            next_url = res.next_url
            if not next_url:
                break
            res = self.request(next_url).get()
        return results

    def request(self, *urls, **kwargs):
        """Creates a new CloudControllerRequest object with the API version
        prepended to the url segments specified.

        V2 API does not provide API urls with scheme://hostname/v2/ prepended.
        V3 API does provide API urls with scheme://hostname/v3/ prepended.

        This function strips https?://hostname/v\d+/ from the urls[0] argument,
        if len(urls) > 0, so that you may pass a V2 URL path such as /v2/apps
        OR a V3 url such as https://api.example.com/v3/apps and both will
        resolve to /apps. The version supplied in `self.version` will be
        prepended to this resolved path. Any query parameters on urls[0] will
        be preserved in the event that the https?://hostname/v\d+/ is stripped.

        Args:
            *urls: list of URL segments
            **kwargs: supported params include
                v (int): version to use on this request (i.e. 2, 3). Defaults
                    to the internal ``self.version``

        Returns:
            CloudControllerRequest or V3CloudControllerRequest
        """
        version = kwargs.get('v', self.version)
        if version is None or \
                (len(urls) > 0 and re.match('^/?v\d+/', urls[0])):
            return super(CloudController, self).request(*urls)
        else:
            if len(urls) > 0 and re.match('https?://', urls[0]):
                urls = list(urls)
                urls[0] = re.sub('^https?://[^/]+/v\d+/', '', urls[0])
            version_url = ''.join(['v', str(version)])
            return super(CloudController, self).request(version_url, *urls)

    def apps(self, *args):
        """Convenience function passing the ``apps`` url segment.

        Args:
            *args: url segments that will be appended after ``apps``

        Returns:
            CloudControllerRequest
        """
        return self.request('apps', *args)

    def app_usage_events(self, *args):
        """Convenience function passing the ``app_usage_events`` url segment.

        Args:
            *args: url segments that will be appended after
                ``app_usage_events``

        Returns:
            CloudControllerRequest
        """
        return self.request('app_usage_events', *args)

    def service_instances(self, *args):
        """Convenience function passing the ``service_instances`` url segment.

        Args:
            *args: url segments that will be appended after
                ``service_instances``

        Returns:
            CloudControllerRequest
        """
        return self.request('service_instances', *args)

    def services(self, *args):
        """Convenience function passing the ``services`` url segment.

        Args:
            *args: url segments that will be appended after ``services``

        Returns:
            CloudControllerRequest
        """
        return self.request('services', *args)

    def blobstores(self, *args):
        """Convenience function passing the ``blobstores`` url segment.

        Args:
            *args: url segments that will be appended after ``blobstores``

        Returns:
            CloudControllerRequest
        """
        return self.request('blobstores', *args)

    def buildpacks(self, *args):
        """Convenience function passing the ``buildpacks`` url segment.

        Args:
            *args: url segments that will be appended after ``buildpacks``

        Returns:
            CloudControllerRequest
        """
        return self.request('buildpacks', *args)

    def events(self, *args):
        """Convenience function passing the ``events`` url segment.

        Args:
            *args: url segments that will be appended after ``events``

        Returns:
            CloudControllerRequest
        """
        return self.request('events', *args)

    def quota_definitions(self, *args):
        """Convenience function passing the ``quota_definitions`` url segment.

        Args:
            *args: url segments that will be appended after
                ``quota_definitions``

        Returns:
            CloudControllerRequest
        """
        return self.request('quota_definitions', *args)

    def organizations(self, *args):
        """Convenience function passing the ``organizations`` url segment.

        Args:
            *args: url segments that will be appended after ``organizations``

        Returns:
            CloudControllerRequest
        """
        return self.request('organizations', *args)

    def private_domains(self, *args):
        """Convenience function passing the ``private_domains`` url segment.

        Args:
            *args: url segments that will be appended after ``private_domains``

        Returns:
            CloudControllerRequest
        """
        return self.request('private_domains', *args)

    def routes(self, *args):
        """Convenience function passing the ``routes`` url segment.

        Args:
            *args: url segments that will be appended after ``routes``

        Returns:
            CloudControllerRequest
        """
        return self.request('routes', *args)

    def security_groups(self, *args):
        """Convenience function passing the ``security_groups`` url segment.

        Args:
            *args: url segments that will be appended after ``security_groups``

        Returns:
            CloudControllerRequest
        """
        return self.request('security_groups', *args)

    def service_bindings(self, *args):
        """Convenience function passing the ``service_bindings`` url segment.

        Args:
            *args: url segments that will be appended after
                ``service_bindings``

        Returns:
            CloudControllerRequest
        """
        return self.request('service_bindings', *args)

    def service_brokers(self, *args):
        """Convenience function passing the ``service_brokers`` url segment.

        Args:
            *args: url segments that will be appended after ``service_brokers``

        Returns:
            CloudControllerRequest
        """
        return self.request('service_brokers', *args)

    def service_plan_visibilities(self, *args):
        """Convenience function passing the ``service_plan_visibilities`` url
        segment.

        Args:
            *args: url segments that will be appended after
                ``service_plan_visibilities``

        Returns:
            CloudControllerRequest
        """
        return self.request('service_plan_visibilities', *args)

    def service_plans(self, *args):
        """Convenience function passing the ``service_plans`` url segment.

        Args:
            *args: url segments that will be appended after ``service_plans``

        Returns:
            CloudControllerRequest
        """
        return self.request('service_plans', *args)

    def shared_domains(self, *args):
        """Convenience function passing the ``shared_domains`` url segment.

        Args:
            *args: url segments that will be appended after ``shared_domains``

        Returns:
            CloudControllerRequest
        """
        return self.request('shared_domains', *args)

    def space_quota_definitions(self, *args):
        """Convenience function passing the ``space_quota_definitions`` url
        segment.

        Args:
            *args: url segments that will be appended after
                ``space_quota_definitions``

        Returns:
            CloudControllerRequest
        """
        return self.request('space_quota_definitions', *args)

    def spaces(self, *args):
        """Convenience function passing the ``spaces`` url segment.

        Args:
            *args: url segments that will be appended after ``spaces``

        Returns:
            CloudControllerRequest
        """
        return self.request('spaces', *args)

    def stacks(self, *args):
        """Convenience function passing the ``stacks`` url segment.

        Args:
            *args: url segments that will be appended after ``stacks``

        Returns:
            CloudControllerRequest
        """
        return self.request('stacks', *args)

    def users(self, *args):
        """Convenience function passing the ``users`` url segment.

        Args:
            *args: url segments that will be appended after ``users``

        Returns:
            CloudControllerRequest
        """
        return self.request('users', *args)

    def resource_match(self, *args):
        """Convenience function passing the ``resource_match`` url segment.

        Args:
            *args: url segments that will be appended after ``resource_match``

        Returns:
            CloudControllerRequest
        """
        return self.request('resource_match', *args)

    @classmethod
    def new_instance(cls, **kwargs):
        return new_cloud_controller(cloud_controller_class=cls, **kwargs)


class UAA(RequestFactory):
    """Provides base functions for building UAA requests
    """
    _access_token = None
    _refresh_token = None
    _client_id = None
    _client_secret = None

    def __init__(self, base_url, client_id=None, client_secret=None):
        super(UAA, self).__init__()
        self.accept_json()
        self.set_base_url(base_url)
        self.set_client_credentials(client_id, client_secret)

    @property
    def access_token(self):
        """Deprecated. **DO NOT USE!**
        """
        _print_deprecated_message('UAA.access_token', 'UAA.get_access_token()')
        return self._access_token

    @property
    def client_id(self):
        """Get the internal client ID

        Returns:
            str
        """
        return self._client_id

    @property
    def client_secret(self):
        """Get the internal client secret

        Returns:
            str
        """
        return self._client_secret

    def get_access_token(self):
        """Get the internal access token

        Returns:
            JWT
        """
        return self._access_token

    def get_refresh_token(self):
        """Get the internal refresh token

        Returns:
            JWT
        """
        return self._refresh_token

    def set_client_credentials(self, client_id, client_secret,
                               set_basic_auth=False):
        """Set the internal client ID and secret

        Args:
            client_id (str): UAA client id
            client_secret (str): UAA client secret
            set_basic_auth (bool): if true, this will set the client ID and
                secret in the Authorization as basic auth
        """
        self._client_id = client_id
        self._client_secret = client_secret
        if self._client_id is not None and \
                self._client_secret is not None and \
                set_basic_auth:
            self.set_basic_auth(client_id, client_secret)
        return self

    def set_access_token(self, access_token):
        """Set the internal access token

        Args:
            access_token (str)

        Returns:
            UAA
        """
        if not isinstance(access_token, JWT):
            access_token = JWT(access_token)
        self._access_token = access_token
        return self

    def set_refresh_token(self, refresh_token):
        """Set the internal refresh token

        Args:
            refresh_token (str)

        Returns:
            UAA
        """
        if not isinstance(refresh_token, JWT):
            refresh_token = JWT(refresh_token)
        self._refresh_token = refresh_token
        return self

    def update_tokens(self, res):
        """Accepts a response object from the UAA Token Authorization API and
        updates this object with access_token and response_token.

        Args:
            res: Expects res.data['access_token'] and (optionally)
                res.data['refresh_token'] to be set.
        """
        if res.has_error:
            res.raise_error()
        self.set_access_token(res.data['access_token'])
        if 'refresh_token' in res.data:
            self.set_refresh_token(res.data['refresh_token'])

    def with_authorization(self):
        """Deprecated. **DO NOT USE!**
        """
        _print_deprecated_message('uaa.with_authorization()',
                                  'uaa.client_credentials()')
        return self.client_credentials()

    def client_credentials(self):
        """Sends a request for client_credentials grant_type

        Request parameters::

            POST /oauth/token
            Accept: application/json

                response_type = 'token',
                grant_type = 'client_credentials',

        Returns:
            Response
        """
        return self.request('oauth/token').accept_json().set_params(
            response_type='token',
            grant_type='client_credentials',
        ).post()

    def password_grant(self, username, password):
        """Sends a request for password grant_type

        Request parameters::

            POST /oauth/token
            Accept: application/json

                response_type = 'token'
                grant_type = 'password'
                client_id = self._client_id
                client_secret = self._client_secret
                username = username
                password = password

        Returns:
            Response
        """
        return self.request('oauth/token').accept_json().set_params(
            response_type='token',
            grant_type='password',
            client_id=self._client_id,
            client_secret=self._client_secret,
            username=username,
            password=password,
        ).post()

    def refresh_token(self, refresh_token=None):
        """Sends a request for refresh_token grant_type. This will use the
        internally set _refresh_token if the refresh_token arg is not set

        Request parameters::

            POST /oauth/token
            Accept: application/json

                grant_type = 'refresh_token',
                client_id = self._client_id,
                client_secret = self._client_secret,
                refresh_token = str(refresh_token or self._refresh_token)

        Args:
            refresh_token (str|None): set a specific refresh token to be used.

        Returns:
            Response
        """
        return self.request('oauth/token').set_params(
            grant_type='refresh_token',
            client_id=self._client_id,
            client_secret=self._client_secret,
            refresh_token=str(refresh_token or self._refresh_token)
        ).post()

    def token_key(self):
        """Gets the token key for the internally set client_id

        Returns:
            Response
        """
        return self.request('token_key').get()

    def authorization_code(self,
                           code,
                           response_type,
                           redirect_uri=None,
                           **kwargs):
        """Sends a request for the authorization_code grant_type to acquire an
        access_token

        Request parameters::

            POST /oauth/token
            Accept: application/json

                code = code
                response_type = response_type
                grant_type = 'authorization_code'
                redirect_uri = redirect_uri

        Args:
            code (str): one time use code passed by UAA to the redirect_uri
                after successful user login at UAA
            response_type (str): must be the response_type string used to
                acquire the code
            redirect_uri (str|None): must be the redirect_uri used to acquire
                the code
            **kwargs (dict): any custom request body parameters

        Returns:
            Response
        """
        kwargs.update(
            code=code,
            response_type=response_type,
            grant_type='authorization_code',
        )
        if redirect_uri is not None:
            kwargs['redirect_uri'] = redirect_uri
        return self.request('oauth/token').set_params(**kwargs).post()

    def authorization_code_url(self, response_type, scope=None,
                               redirect_uri=None, state=None, **kwargs):
        """The following list summarizes the various authorization code flows
        in the UAA docs.::

            Browser Flow:
                response_type='code', scope='...',
                redirect_uri='http://localhost/auth'

            API Flow:
                response_type='code', state='somerandomstr',
                redirect_uri='http://localhost/auth'

            Hybrid Flow:
                response_type='id_token code',
                redirect_uri='http://localhost/auth'

            OpenID Connect Flow:
                response_type='id_token', scope='...',
                redirect_uri='http://localhost/auth'

                response_type='token id_token', scope='...',
                redirect_uri='http://localhost/auth'

        Args:
            response_type (str): valid response type strings (code, id_token,
                token)
            scope (str|list[str]|None): any scope strings you need
            redirect_uri (str|None): redirect URI that will receive the auth
                code
            state (str|None): used in API flow
            kwargs (dict): any additional request body params

        Returns:
             str: a URI to redirect the user for login with UAA. On successful
                 login, UAA will redirect to redirect_uri with a "code" query
                 parameter containing a one time use code. The code is handled
                 by the ``self.authorization_code()`` token function.
        """
        kwargs.update(
            response_type=response_type,
            client_id=self._client_id,
        )
        query = [(k, v) for k, v in kwargs.items()]
        query.extend([('response_type', response_type),
                      ('client_id', self._client_id)])
        if isinstance(scope, string_types):
            scope = [scope]
        if isinstance(scope, list):
            query.append(('scope', '+'.join(scope)))
        if redirect_uri is not None:
            query.append(('redirect_uri', redirect_uri))
        if state is not None:
            query.append(('state', state))

        return '?'.join([self.get_url('oauth/authorize'), urlencode(query)])

    def verify_token(self, token, **decode_kwargs):
        """Verifies the OAuth2 Token (or ID Token) using the client's public
        key.

        Args:
            token (str): oauth token to be verified
            decode_kwargs (dict): keyword args for jwt.decode(**kwargs). This
                is useful for specifying conditions of verification.

        Returns:
            dict: contents of the JWT
        """
        res = self.token_key()
        key = res.data['value']
        return jwt.decode(
            token,
            key=key,
            verify=True,
            **decode_kwargs
        )

    def one_time_password(self, client_id=None):
        client_id = client_id or self.client_id
        req = self.request('oauth/authorize')\
            .application_json()\
            .accept_json()\
            .set_query(client_id=client_id, response_type='code')\
            .set_bearer_auth(self.get_access_token().to_string())\
            .set_custom_requests_args(allow_redirects=False)
        res = req.get()
        if 302 != res.response.status_code:
            raise exc.CFException(
                'Not authorized ({0})'.format(res.response.status_code), 403)
        loc = res.headers.get('location', None)
        if not loc:
            raise exc.CFException('Not authorized (no redirect)', 403)
        qs = parse_qs(urlparse(loc).query)
        code = qs.get('code', [None])[0]
        if not code:
            raise exc.CFException('Not authorized (no code)', 403)
        return code


class JWT(object):
    """Wrapper around the JWT object
    """

    def __init__(self, token_str, verify=False, **verify_kwargs):
        self.token = token_str
        self.attrs = jwt.decode(token_str, verify=verify, **verify_kwargs)

    def __getattr__(self, item):
        """This getter extracts keys from the JWT's internal dict. If a key
        is not found in the JWT, then return None

        Args:
            item (str)

        Returns:
            int|str|None
        """
        return self.attrs.get(item, None)

    def __str__(self):
        return self.token

    def to_string(self):
        """Get the original string representation of the token
        """
        return self.__str__()

    @property
    def is_expired(self):
        """Indicates if the token is expired
        """
        return int(time.time()) >= self.attrs['exp']


class Doppler(RequestFactory):
    """Provides base functions for building Doppler/Loggregator API endpoints
    """
    websocket_class = None

    def __init__(self, base_url, websocket_class=WebSocket):
        super(Doppler, self).__init__()
        self.set_base_url(base_url).set_websocket_class(websocket_class)

    def set_websocket_class(self, websocket_class):
        """Sets the internal websocket wrapper class

        Args:
            websocket_class (WebSocket|callable): websocket class wrapper

        Returns:
            self (Doppler)
        """
        self.websocket_class = websocket_class
        return self

    def apps(self, first, *url):
        """Create a new request object using the url segments

        Args:
            first (str): required url segment
            url (tuple[str]): optional url segments

        Returns:
            Request
        """
        return self.request('apps', first, *url)

    def ws_request(self, first, *url):
        """Create a new WebSocket instance using the url segments

        Args:
            first (str): required url segment
            url (tuple[str]): optional url segments

        Returns:
            WebSocket
        """
        doppler_url = self.request(first, *url).base_url
        doppler_url = re.sub('^http(s?):', 'ws\\1:', doppler_url, count=1)
        return self.websocket_class(doppler_url, verify_ssl=self.verify_ssl,
                                    **self.headers)


class CFInfo(object):
    def __init__(self, cc):
        self.data = cc.request('v2/info').get().data

    @property
    def uaa_url(self):
        """The base URL for UAA

        Returns:
            str
        """
        return self.data['token_endpoint']

    @property
    def doppler_url(self):
        """The base URL for Doppler

        Returns:
            str
        """
        return self.data['doppler_logging_endpoint']

    @property
    def ssh_url(self):
        """The base SSH proxy url

        Returns:
            str
        """
        return self.data['app_ssh_endpoint']

    @property
    def ssh_client_id(self):
        """The client ID to be used in authenticating with UAA before using
        the SSH proxy

        Returns:
            str
        """
        return self.data['app_ssh_oauth_client']

    @property
    def ssh_host_key_fingerprint(self):
        """The SSH proxy host key fingerprint to verify when connecting to
        an application instance via SSH

        Returns:
            str
        """
        return self.data['app_ssh_host_key_fingerprint']


class SSHProxy(object):
    def __init__(self, uaa, ssh_proxy, client_id, fingerprint):
        if '//' not in ssh_proxy:
            ssh_proxy = ''.join(['//', ssh_proxy])
        parts = urlparse(ssh_proxy)
        self.uaa = uaa
        self.host = parts.hostname
        self.port = int(parts.port if parts.port is not None else 22)
        self.client_id = client_id
        self.fingerprint = fingerprint


def decode_jwt(access_token):
    """Decodes a JWT (UAA Access Tokens) without verifying the signature.

    Returns:
        dict
    """
    return jwt.decode(access_token, verify=False, algorithms='RS256')


def new_uaa(
        cc=None,
        base_url=None,
        verify_ssl=None,
        validate_ssl=None,
        username=None,
        password=None,
        client_id=None,
        client_secret=None,
        authorization_code=None,
        refresh_token=None,
        access_token=None,
        no_auth=False,
        cloud_controller_class=None,
        uaa_class=None,
):
    """Creates a new UAA client object. This function requires args base_url OR
    cc; base_url takes precedence over cc. If base_url not given, then cc must
    be an instance of str or CloudController. If an instance of str, then it's
    converted into an instance of CloudController. CloudController.info().get()
    is called to get the UAA endpoint.

    If no other authorization method is set, then client_credentials
    authorization will be attempted with the client_id and secret; however, if
    no_auth=True is passed, then no authorization will be attempted.

    This method supports environment variable settings if some required
    arguments are left blank.  See cc, client_id, client_secret, and
    verify_ssl.

    Args:
        cc (str|CloudController|None):
            optional(if base_url is set), defaults to env var PYTHON_CF_URL.
            If base_url is passed, then this value is ignored
        client_id (str|None):
            required, defaults to env var PYTHON_CF_CLIENT_ID
        client_secret (str|None):
            required, defaults to env var PYTHON_CF_CLIENT_SECRET
        verify_ssl (bool|None):
            optional, defaults to env var !PYTHON_CF_IGNORE_SSL
        base_url (str):
            optional if cc is set, sets the UAA base endpoint url
        username (str):
            optional, user's name
        password (str):
            optional, user's password
        authorization_code (dict):
            optional, authorization_code method arguments. Setting this
            triggers the authorization_code() authorization method
        refresh_token (str):
            optional, refresh token string. Setting this will also trigger
            the refresh_token() authorization method. But if access_token is
            set, then the refresh token auth method will not be triggered, and
            the refresh token will be set on the UAA object.
        access_token (str):
            optional, access token string. If set, this set the access_token
            on the UAA object that is returned. If refresh_token is passed,
            then that will be set on the UAA object as well.
        no_auth (bool):
            optional, indicates to skip authorizing UAA. Neither access_token
            nor refresh_token will be set if this value is True.
        validate_ssl (bool|None):
            **DEPRECATED** use verify_ssl **DEPRECATED**

    Returns:
        UAA
    """
    if validate_ssl is not None:
        _print_deprecated_message('validate_ssl in (cf_api.new_uaa)',
                                  'verify_ssl in (cf_api.new_uaa)')
        verify_ssl = validate_ssl

    client_id = _get_default_var(client_id, 'PYTHON_CF_CLIENT_ID')
    client_secret = _get_default_var(client_secret, 'PYTHON_CF_CLIENT_SECRET')
    verify_ssl = os.getenv('PYTHON_CF_IGNORE_SSL', '') != 'true' \
        if verify_ssl is None else verify_ssl

    if not isinstance(client_id, string_types) or \
            not client_id or \
            not isinstance(client_secret, string_types):
        raise exc.InvalidArgsException('Invalid UAA client credentials', 500)

    if cloud_controller_class is None:
        cloud_controller_class = CloudController

    if uaa_class is None:
        uaa_class = UAA

    if not base_url:
        cc = _get_default_var(cc, 'PYTHON_CF_URL')
        if isinstance(cc, str):
            cc = cloud_controller_class(cc).set_verify_ssl(verify_ssl)
            cc.set_info(CFInfo(cc))
        base_url = cc.info.uaa_url

    uaa = uaa_class(base_url)\
        .set_verify_ssl(verify_ssl)\
        .set_client_credentials(client_id, client_secret, set_basic_auth=True)

    if no_auth:
        res = None

    elif username and password:
        res = uaa.password_grant(
            username,
            password
        )

    elif authorization_code:
        if not isinstance(authorization_code, dict):
            raise exc.InvalidArgsException(
                'authorization_code must be an instance of dict', 500)
        res = uaa.authorization_code(**authorization_code)

    elif access_token:
        uaa.set_access_token(access_token)
        if refresh_token:
            uaa.set_refresh_token(refresh_token)
        res = None

    elif refresh_token:
        res = uaa.refresh_token(refresh_token)

    else:
        res = uaa.client_credentials()

    if res is not None:
        uaa.update_tokens(res)

    return uaa


def new_doppler(cc=None, base_url=None, verify_ssl=None, access_token=None):
    """Sets a the doppler base endpoint on this client. If cc is set, then all
    other args will be ignored.

    Args:
        cc (CloudController|None):  initialized cloud controller instance
        base_url (str|None):        base doppler url
        verify_ssl (bool|None):     verify SSL certs
        access_token (str|None):    access token string

    Returns:
        self (Doppler)
    """
    if not base_url:
        if not isinstance(cc, CloudController):
            raise exc.InvalidArgsException(
                'cc must be an instance of CloudController', 500)

        if not isinstance(cc.uaa, UAA):
            raise exc.InvalidStateException(
                'cc UAA client is not set on Cloud Controller', 500)

        base_url = cc.info.doppler_url
        access_token = cc.uaa.get_access_token().to_string()
        verify_ssl = cc.verify_ssl

    base_url = re.sub('^ws(s?):', 'http\\1:', base_url, count=1)

    return Doppler(base_url)\
        .set_verify_ssl(verify_ssl)\
        .set_bearer_auth(access_token)


def new_cloud_controller(
        base_url=None,
        validate_ssl=None,
        verify_ssl=None,
        username=None,
        password=None,
        client_id=None,
        client_secret=None,
        init_doppler=False,
        authorization_code=None,
        refresh_token=None,
        access_token=None,
        no_auth=False,
        version=2,
        cloud_controller_class=None,
        uaa_class=None,
        **kwargs
):
    """Creates a new Cloud Controller client object AND attempts to get an
    Access Token from UAA using the user and/or client credentials. If
    username/password is given then the password grant_type will be used,
    otherwise, the client_credentials grant_type will be used.

    The following arguments will default to the environment variable settings

    Args:
        base_url (str):
            required, defaults to env var PYTHON_CF_URL
        client_id (str|None):
            required, defaults to env var PYTHON_CF_CLIENT_ID
        client_secret (str|None):
            required, defaults to env var PYTHON_CF_CLIENT_SECRET
        verify_ssl (bool|None):
            optional, defaults to env var !PYTHON_CF_IGNORE_SSL
        username (str|None):
            optional, see new_uaa()
        password (str|None):
            optional, see new_uaa()
        authorization_code (dict|None):
            optional, see new_uaa()
        refresh_token (str|None):
            optional, see new_uaa()
        access_token (str|None):
            optional, see new_uaa()
        no_auth (bool|None):
            optional, see new_uaa()
        validate_ssl (bool|None):
            **DEPRECATED** use verify_ssl **DEPRECATED**
    Returns:
        CloudController
    """
    if validate_ssl is not None:
        _print_deprecated_message(
            'validate_ssl in (cf_api.new_cloud_controller)',
            'verify_ssl in (cf_api.new_cloud_controller)')
        verify_ssl = validate_ssl

    base_url = _get_default_var(base_url, 'PYTHON_CF_URL')
    verify_ssl = os.getenv('PYTHON_CF_IGNORE_SSL', '') != 'true' \
        if verify_ssl is None else verify_ssl

    if cloud_controller_class is None:
        cloud_controller_class = CloudController

    cc = cloud_controller_class(base_url).set_verify_ssl(verify_ssl)
    if version == 3:
        cc.set_v3()
    else:
        cc.set_version(version)

    info = CFInfo(cc)
    cc.set_info(info)

    uaa = new_uaa(
        base_url=cc.info.uaa_url,
        verify_ssl=verify_ssl,
        username=username,
        password=password,
        client_id=client_id,
        client_secret=client_secret,
        authorization_code=authorization_code,
        refresh_token=refresh_token,
        access_token=access_token,
        no_auth=no_auth,
        cloud_controller_class=cloud_controller_class,
        uaa_class=uaa_class,
    )

    cc.set_uaa(uaa)
    if uaa.get_access_token():
        cc.set_bearer_auth(uaa.get_access_token().to_string())

        doppler = new_doppler(
            base_url=cc.info.doppler_url,
            verify_ssl=verify_ssl,
            access_token=uaa.get_access_token().to_string()
        )
        cc.set_doppler(doppler)
    elif not no_auth:
        raise exc.InvalidStateException('Unable to authorize with UAA', 401)

    if uaa.get_access_token():
        ssh_proxy = SSHProxy(
            uaa,
            cc.info.ssh_url,
            cc.info.ssh_client_id,
            cc.info.ssh_host_key_fingerprint
        )
        cc.set_ssh_proxy(ssh_proxy)

    return cc
