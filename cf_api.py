# Copyright 2020 Philips HSDP
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
from __future__ import print_function
import re
import os
import sys
import json
import time
import requests
import argparse
from base64 import b64decode
from requests.exceptions import HTTPError
if sys.version_info[0] == 2:
    from urllib import urlencode
    from urlparse import urlsplit, urlunsplit
else:
    from urllib.parse import urlencode, urlsplit, urlunsplit


resource_names = [
    'app_usage_events',
    'apps',
    'audit_events',
    'buildpacks',
    'builds',
    'blobstores',
    'deployments',
    'domains',
    'droplets',
    'events',
    'environment_variable_groups',
    'feature_flags',
    'info',
    'isolation_segments',
    'jobs',
    'organizations',
    'packages',
    'private_domains',
    'processes',
    'quota_definitions',
    'resource_match',
    'running_security_groups',
    'roles',
    'route_mappings',
    'routes',
    'security_groups',
    'service_instances',
    'service_bindings',
    'service_brokers',
    'service_keys',
    'service_plan_visibilities',
    'service_plans',
    'service_usage_events',
    'services',
    'shared_domains',
    'space_quota_definitions',
    'spaces',
    'staging_security_groups',
    'stacks',
    'tasks',
    'user_provided_service_instances',
    'users',
]


def jwt_decode(jwt):
    """Decodes a JWT token. It is useful primarily to introspect a UAA JWT
    token without making a request to UAA.

    WARNING: jwt_decode() does NOT verify the token's signature. DO NOT rely on
    this to verify a token signature.

    Args:
        jwt (str): JWT token string

    Returns:
        dict: A dictionary of the token's attributes"""
    parts = jwt.split('.', 2)
    if len(parts) != 3:
        raise RequestException('JWT is invalid: {}'.format(jwt))
    # add extra padding (==) to avoid b64decode errors
    data = b64decode((parts[1] + '==')).decode('utf-8')
    data = json.loads(data)
    return data


def is_expired(jwt, now):
    data = jwt_decode(jwt)
    if 'exp' not in data:
        raise RequestException('JWT expiration not found: {}'.format(data))
    return int(data['exp']) <= now


class RequestException(Exception):
    request = None

    def __init__(self, msg, request=None):
        super(RequestException, self).__init__(msg)
        self.request = request


class ResponseException(Exception):
    response = None
    error = None

    def __init__(self, msg, error=None):
        super(ResponseException, self).__init__(msg)
        self.error = error
        if error is not None:
            self.response = error.response


class ConfigException(Exception):
    config = None

    def __init__(self, msg, config=None):
        super(ConfigException, self).__init__(msg)
        self.config = config


def configure(config):
    """Configure makes an initial request to the /v2/info API endpoint to
    configure the authentication and other endpoints.

    Args:
        config (Config)

    Returns:
        Config: the original config argument"""
    config.info = None
    config.auth = None
    url = '/'.join([config.base_url, 'v2/info'])
    try:
        res = requests.get(url)
        res.raise_for_status()
    except HTTPError as e:
        raise ResponseException('Error configuring {}.'
                                .format(e.response.status_code), e)
    config.info = json.loads(res.content)
    return config


def build_authentication_request(config):
    """Builds an OAuth authentication request to send to UAA. The rules are as
    follows:

    1) if username and password are set, then
        a) if we don't have a token, then use grant_type=password
        b) else if we have refresh_token, then use grant_type=refresh_token
        c) else raise ConfigException
    2) else try grant_type=client_credentials

    Args:
        config (Config)

    Returns:
        dict: containing the parameters for the UAA OAuth request
    """
    data = {'client_id': config.client_id,
            'client_secret': config.client_secret}
    if config.username is not None and config.password is not None:
        if config.auth is None:
            data['grant_type'] = 'password'
            data['username'] = config.username
            data['password'] = config.password
        elif 'refresh_token' in config.auth:
            data['grant_type'] = 'refresh_token'
            data['refresh_token'] = config.auth['refresh_token']
        else:
            raise RequestException('Unable to build authentication request.')
    else:
        data['grant_type'] = 'client_credentials'
    return data


def authenticate(config, data):
    """Authenticate performs a login against UAA.

    Args:
        config (Config): configuration containing login endpoint
        data (dict): a dictionary containing the login credentials
            created by ``build_authentication_request()``
    Returns:
        Config: the original config argument"""
    config.assert_info()
    headers = {'Content-Type': 'application/x-www-form-urlencoded'}
    data = urlencode(data).encode('utf-8')
    url = '/'.join([config.info['token_endpoint'], 'oauth/token'])
    try:
        res = requests.request('POST', url, data=data, headers=headers)
        res.raise_for_status()
    except HTTPError as e:
        raise ResponseException('Error authenticating {}.'
                                .format(e.response.status_code), e)
    config.auth = json.loads(res.content)
    return config


class Config(object):
    """Config encapsulates the global settings for a single Cloud Foundry API
    endpoint"""

    base_url = os.getenv('CF_URL')
    """The API base url; read from environment var CF_URL
    """

    version = os.getenv('CF_VERSION', 'v2')
    """The API version; read from environment var CF_VERSION; defaults to v2
    """

    username = os.getenv('CF_USERNAME')
    """The API username; read from environment var CF_USERNAME
    """

    password = os.getenv('CF_PASSWORD')
    """The API password; read from environment var CF_PASSWORD
    """

    client_id = os.getenv('CF_CLIENT_ID', 'cf')
    """The API client ID; read from environment var CF_CLIENT_ID;
    defaults to 'cf'
    """

    client_secret = os.getenv('CF_CLIENT_SECRET', '')
    """The API client secret; read from environment var CF_CLIENT_SECRET;
    defaults to ''
    """

    auto_refresh_token = os.getenv('CF_AUTO_REFRESH_TOKEN', 'true') != 'false'
    """Indicates whether to attempt to automatically refresh the API
    access_token
    """

    request_class = None
    """May optionally contain a user-specified request class that will
    be used to build request
    """

    info = None
    """Contains a dictionary of /v2/info details
    """

    auth = None
    """Contains a dictionary of UAA auth details
    """

    def assert_info(self):
        if self.info is None:
            raise ConfigException('Config info is required. '
                                  'Run `configure()\' on this and try again.')

    def assert_auth(self):
        self.assert_info()
        if self.auth is None:
            raise ConfigException('Config auth is required. Run '
                                  '`authenticate()\' on this and try again.')


class Resource(object):
    """Resource wraps an individual API object providing a handful
    of helper attributes for accessing common API object keys such as:
        guid, name, space_guid, organization_guid"""

    data = None

    def __init__(self, data):
        self.data = data

    def get(self, name):
        """Access a key from the resource's data dictionary"""
        return self.data.get(name)

    def __repr__(self):
        """Shows the guid and name/host/label of this object"""
        name = str(self.host or self.label or self.name)
        return '\t'.join([str(self.guid), name])

    def __getattr__(self, name):
        """Access a key from the resource's data dictionary"""
        return self.get(name)

    def __getitem__(self, name):
        """Access a key from the resource's data dictionary"""
        return self.get(name)

    def __contains__(self, name):
        """Checks if key is in the resource's data dictionary"""
        return self.get(name) is not None


class V2Resource(Resource):
    """V2Resource wraps a v2 API object."""

    def get(self, name):
        """Access a key from the resource's data dictionary

        If <name> matches .metadata or .entity:
            .<name> is returned
        If <name> matches *_url or *_guid:
            .entity.<name> is returned if it exists else None
        If <name> is in .entity:
            .entity.<name> is returned
        If <name> is in .metadata:
            .metadata.<name> is returned
        Else
            super.get() is returned
        """
        if name == 'entity' or name == 'metadata':
            return self.data[name]
        elif name.endswith('_url') or name.endswith('_guid'):
            return self.data['entity'].get(name)
        elif name in self.data['entity']:
            return self.data['entity'][name]
        elif name in self.data['metadata']:
            return self.data['metadata'][name]
        else:
            return super(V2Resource, self).get(name)


class V3Resource(Resource):
    """V3Resource wraps a v3 API object."""

    def get(self, name):
        """Access a key from the resource's data dictionary

        If <name> matches *_url:
            .link.<name>.href is returned if it exists else None
        If <name> matches *_guid:
            .relationships.<name>.data.guid is returned if it exists else None
        Else
            super.get() is returned"""
        if name.endswith('_url'):
            if 'links' not in self.data:
                return None
            parts = name.split('_')
            name = '_'.join(parts[:-1])
            if name not in self.data['links']:
                return None
            return self.data['links'][name]['href']
        elif name.endswith('_guid'):
            if 'relationships' not in self.data:
                return None
            parts = name.split('_')
            name = '_'.join(parts[:-1])
            if name not in self.data['relationships']:
                return None
            return self.data['relationships'][name]['data']['guid']
        else:
            return super(V3Resource, self).get(name)


class Response(object):
    """Response wraps an API response providing checks for errors and
    simplified methods for accessing returned resources."""

    resource_class = Resource
    """Indicates the *Resource wrapper class that should be used to wrap
    individual API resources"""

    response = None
    """Holds underlying requests.Response object"""

    data = None
    """Holds a JSON parsed dictionary of response content"""

    def __init__(self, response):
        self.response = response
        self.data = json.loads(response.content)

    def __dir__(self):
        names = ['next_url', 'prev_url', 'total_results', 'total_pages']
        names.extend(dir(self.__class__))
        return names

    def assert_ok(self):
        raise ConfigException('Response.assert_ok() not implemented.')

    @property
    def ok(self):
        """Indicates whether the response was successful"""
        return 200 <= self.response.status_code < 300

    @property
    def resources(self):
        """Returns a list of Resource wrapped API objects. If `resources\'
        was set, then return the full list. If only a single resource was
        returned, then wrap that resource in a list. The `resource_class\'
        attribute is used to wrap all underlying API objects."""
        self.assert_ok()
        if 'resources' in self.data:
            return [self.resource_class(r)
                    for r in self.data.get('resources', [])]
        else:
            return [self.resource_class(self.data)]

    @property
    def resource(self):
        """Returns a Resource wrapped API object. If `resources\' was set,
        then return the first list item; if the list is empty, then raise
        `ResponseException\' to indicate this. If only a single resource was
        returned, then return that resource. The `resource_class\' attribute
        is used to wrap the returned API object."""
        self.assert_ok()
        if 'resources' in self.data:
            try:
                return self.resource_class(next(iter(self.data['resources'])))
            except StopIteration:
                raise ResponseException('Resource not found.', self)
        else:
            return self.resource_class(self.data)


class V2Response(Response):
    """V2Response wraps a v2 API response, providing access to the `next_url\'
    attr and error checks."""

    resource_class = V2Resource
    """Indicates the V2Resource wrapper class that should be used to wrap
    individual API resources.
    """

    def __getattr__(self, name):
        """Access a key from the response's data dictionary"""
        return self.data.get(name)

    def assert_ok(self):
        if not self.ok:
            if 'error_code' in self.data:
                msg = self.data['error_code']
            else:
                msg = str(self.response)
            msg = 'HTTP {} {}'.format(self.response.status_code, msg)
            msg = 'An API error occurred: {}.'.format(msg)
            raise ResponseException(msg, self)


class V3Response(Response):
    """V3Response wraps a v3 API response, providing access to the `next_url\'
    attr and error checks."""

    resource_class = V3Resource
    """Indicates the V3Resource wrapper class that should be used to wrap
    individual API resources"""

    def __getattr__(self, name):
        """Access a key from the response's data dictionary

        If <name> matches *_url:
            .pagination.<name>.href is returned if it exists else None
        If <name> is ``total_pages`` or ``total_results``
            .pagination.<name> is returned if it exists else None
        Else
            data[<name>] is returned if it exists else None
        """
        if name.endswith('_url'):
            if 'pagination' not in self.data:
                return None
            parts = name.split('_')
            name = '_'.join(parts[:-1])
            return self.data['pagination'][name].get('href')
        elif name == 'total_pages' or name == 'total_results':
            return self.data['pagination'].get(name)
        else:
            return self.data.get(name)

    def assert_ok(self):
        if not self.ok:
            if 'errors' in self.data:
                msg = ' - '.join([
                    self.data['errors'][0]['title'],
                    self.data['errors'][0]['detail'],
                ])
            else:
                msg = str(self.response)
            msg = 'HTTP {} {}'.format(self.response.status_code, msg)
            msg = 'An API error occurred: {}.'.format(msg)
            raise ResponseException(msg, self)


class Request(object):
    """Request wraps an API request by encapsulating the request components
    such as HTTP method, body, and URL"""

    response_class = Response
    """Indicates *Response class that should be used to wrap API responses
    received."""

    config = None
    """Indicates the API config"""

    body = None
    """Indicates the HTTP body; must be bytes encoded"""

    url = None
    """Indicates the HTTP endpoint to request; use ``set_url()`` to control
    this value"""

    version = None

    def __init__(self, config, *path, **query):
        self.config = config
        self.headers = {}
        if self.version is None:
            self.version = config.version
        self.set_url(*path, **query)

    def __dir__(self):
        names = []
        names.extend(dir(self.__class__))
        names.extend(resource_names)
        return names

    def __getattr__(self, path):
        """Append a path segment to the URL and return a cloned Request object

        This method enables a fluent style programming for Request,
        for example:

            req = Request(config)
            print(req.apps.url)  # produces http://cfdomain/v2/apps

        In this example, ``apps`` causes invocation of ``__getattr__`` which
        returns a cloned Request object with the path segment ``apps``
        appended.

        Args:
            *path (str): list of path segments

        Returns:
            Request: cloned object"""
        return self.clone().append_path(path)

    def __call__(self, *path):
        """Append multiple path segments to the URL and return a cloned Request
        object

        This method enables a fluent style programming for Request,
        for example:

            guid = '<APPGUID>'
            req = Request(config)
            print(req.apps(guid).url)
            # produces http://cfdomain/v2/apps/<APPGUID>

        In this example, ``apps`` causes invocation of ``__call__`` which
        returns a cloned Request object with the path segment
        ``apps/<APPGUID>`` appended.

        Args:
            *path (str): list of path segments

        Returns:
            Request: cloned object"""
        return self.clone().append_path(*path)

    def append_path(self, *path):
        """Append multiple path segments to this object's URL.

        Args:
            *path (str): list of path segments

        Returns:
            Request"""
        path = '/'.join(list(path))
        parts = list(urlsplit(self.url))
        parts[2] = '/'.join([re.sub('(^/|/$)', '', parts[2]), path])
        self.url = urlunsplit(parts)
        return self

    def set_query(self, **query):
        """Set the object's URL query to the values in **query

        Args:
            **query: dictionary of keys and values to be urlencoded

        Returns:
            Request"""
        parts = list(urlsplit(self.url))
        parts[3] = urlencode(query, doseq=True)
        self.url = urlunsplit(parts)
        return self

    def clone(self):
        """Makes and returns a copy of this request.

        Returns:
            Request: a clone of this request"""
        return self.__class__(self.config, self.url)

    def set_url(self, *path, **query):
        """Sets the URL path and query string for this request. The path
        argument(s) will be
            1) joined with ``/``
            2) stripped of any leading ``scheme://hostname/v\\d+`` prefix
            3) joined with the configured version
            4) have the query string overwritten to match ``**query``, unless
               no query is specified

        Args:
            *path: a list of string URL segments
            **query: key value pairs that should be encoded into the URL string

        Returns:
            Request"""
        path = '/'.join(list(path))
        # The purpose of this replacement is to allow transparent usage of the
        # API's REST URLs, so that when `https://cfhost/v3/apps?page=2` is
        # passed in from .pagination.next.href, no url manips are required.
        # The user may simply pass in the full url, and expect it to be invoked
        # just as if `path = ['apps']` and `query = {'page': 2}`.
        path = re.sub(r'^(https?://[^/]+)?/(v\d+/)?', '', path)
        parts = list(urlsplit(self.config.base_url))
        parts[2] = '/'.join([self.version, path])
        parts[3] = urlencode(query, doseq=True)
        self.url = urlunsplit(parts)
        return self

    def set_body(self, body):
        """Sets the HTTP body to the dict named body.

        Args:
            body (dict): a dictionary of keys and values that will be
                JSON encoded as the request body, encoded to bytes, and stored
                in self.body

        Returns:
            Request"""
        self.body = json.dumps(body).encode('utf-8')
        self.headers['Content-Type'] = 'application/json'
        return self

    def send(self, method, retries=1):
        """Sets the HTTP method for this request. This method will
        automatically try to get a new access token if the access token is
        expired using ``authenticate()``.

        Args:
            method (str): GET, POST, PUT, DELETE, etc.

        Returns:
            Response: this is an instance of self.response_class()"""
        if self.config.auto_refresh_token and (
                self.config.auth is None or
                is_expired(self.config.auth['access_token'], time.time())
        ):
            data = build_authentication_request(self.config)
            authenticate(self.config, data)
        self.config.assert_auth()
        auth = 'bearer {}'.format(self.config.auth['access_token'])
        headers = {'Authorization': auth,
                   'Accept': 'application/json'}
        res = requests.request(method, self.url, data=self.body,
                               headers=headers)
        if res.status_code == 401 and retries > 0:
            configure(self.config)
            return self.send(method, retries - 1)
        return self.response_class(res)

    def get(self):
        """A shortcut that sends this request using HTTP GET method"""
        return self.send('GET')

    def post(self):
        """A shortcut that sends this request using HTTP POST method"""
        return self.send('POST')

    def put(self):
        """A shortcut that sends this request using HTTP PUT method"""
        return self.send('PUT')

    def delete(self):
        """A shortcut that sends this request using HTTP DELETE method"""
        return self.send('DELETE')


class V2Request(Request):
    response_class = V2Response
    version = 'v2'


class V3Request(Request):
    response_class = V3Response
    version = 'v3'


class CloudController(object):
    """CloudController provides a high-level client to build, send, and receive
    v2 or v3 API requests and responses."""

    config = None
    """The config for this client"""

    def __init__(self, config):
        self.config = config

    def __getattr__(self, path):
        """Support fluent style programming by creating a request
        with path segment ``path``. This is an alias for ``request(path)``.

        Args:
            path (str): URL path segment to include in the request

        Returns:
            Request"""
        return self.request(path)

    @property
    def v2(self):
        """Explicitly create a v2 request object

        Returns:
            V2Request"""
        return V2Request(self.config)

    @property
    def v3(self):
        """Explicitly create a v3 request object

        Returns:
            V3Request"""
        return V3Request(self.config)

    @property
    def request_class(self):
        """Picks the correct *Request wrapper class based on
        config.request_class (if set) otherwise
        config.version (i.e. V2Request for ``v2\' or V3Request for ``v3\')"""
        if self.config.request_class is not None:
            return self.config.request_class
        return getattr(sys.modules[__name__],
                       self.config.version.upper() + 'Request')

    def request(self, *path, **query):
        """Creates a request_class instance using the specified
        URL path and query parameters."""
        return self.request_class(self.config, *path, **query)

    def get_space_by_name_v2(self, org_name, space_name):
        orgres = self.request('organizations', q='name:' + org_name).get()
        spaceres = self.request(
            'organizations', orgres.resource.guid, 'spaces',
            q=['name:' + space_name]).get()
        return orgres.resource, spaceres.resource

    def get_space_by_guid_v2(self, guid):
        spaceres = self.request('spaces', guid).get()
        orgres = self.request(
            spaceres.resource['entity']['organization_url']).get()
        return orgres.resource, spaceres.resource

    def get_space_by_name_v3(self, org_name, space_name):
        orgres = self.request('organizations', names=org_name).get()
        spaceres = self.request('spaces', names=space_name,
                                organization_guids=orgres.resource.guid).get()
        return orgres.resource, spaceres.resource

    def get_space_by_guid_v3(self, guid):
        spaceres = self.request('spaces', guid).get()
        orgres = self.request(
            spaceres.resource['links']['organization']['href']).get()
        return orgres.resource, spaceres.resource

    @property
    def get_space_by_guid(self):
        """An API version agnostic function to search for an org and space
        by space guid

        Args:
            space_guid (str)

        Returns:
            tuple[Resource, Resource]:
                Org and space, respectively. Resource class will be chosen
                based on config.version"""
        return getattr(self, 'get_space_by_guid_' + self.config.version)

    @property
    def get_space_by_name(self):
        """An API version agnostic function to search for an org and space
        by org and space name

        Args:
            org_name (str)
            space_name (str)

        Returns:
            tuple[Resource, Resource]:
                Org and space, respectively. Resource class will be chosen
                based on config.version"""
        return getattr(self, 'get_space_by_name_' + self.config.version)


class Space(object):
    """Space is a helper class that provides helper functions to build requests
    that are scoped to a single org and space"""

    cc = None
    """CloudController instance"""

    org = None
    """Resource object representing the organization"""

    space = None
    """Resource object representing the space"""

    def __init__(self, cc):
        self.cc = cc

    def init_by_name(self, org_name, space_name):
        """Initializes org and space by looking them up by their names.

        Args:
            org_name (str)
            space_name (str)

        Returns:
            Space"""
        self.org, self.space = self.cc.get_space_by_name(org_name, space_name)
        return self

    def init_by_guid(self, space_guid):
        """Initializes org and space by looking them up by space_guid.

        Args:
            space_guid (str)

        Returns:
            Space"""
        self.org, self.space = self.cc.get_space_by_guid(space_guid)
        return self

    def request_v2(self, *path, **query):
        return self.cc.request(
            *path, q='space_guid:' + self.space.guid, **query)

    def request_v3(self, *path, **query):
        return self.cc.request(
            *path, space_guids=self.space.guid, **query)

    def request(self, *path, **query):
        """Creates a Request object, wrapped in the approprate version request
        class, with the given URL path and query and automatically appends
        the query parameters required to filter by this space's guid. This
        means that for v2, the query param `q=space_guid:<GUID>\' is set
        on the query string, and for v3, the query param ``space_guids=<GUID>``
        is set on the query string.

        A good use case for this is to query all the apps in a space:

            space = Space(cc)
            space_apps = space.request('apps').get()
            # the v2 URL for this request is /v2/apps?q=space_guid:<GUID>
            # the v3 URL for this request is /v3/apps?space_guids=<GUID>

        Args:
            *path (str): a list of URL path segments
            **query (dict): a dict of query string pairs

        Returns:
            Request:
                a request object of the appropriate version specific class
        """
        return getattr(self, 'request_' + self.cc.config.version)(
            *path, **query)


def iterate_all_resources(req, verbose=False):
    """Gets all the pages of a resource as specified in the given request.
    It invokes the given request as a GET and follows the
    ``next_url`` attribute on each page Response until there are no more pages.
    Each time a new page is fetched, the resources will be individually
    yielded. This function is version agnostic, therefore, v2 or v3 requests
    may be given transparently.

    Args:
        req (Request): the API request object that should be followed
        verbose (bool): indicates to print each page url to stderr;
            this primarily useful in debugging

    Yields:
        Resource"""
    while True:
        if verbose:
            print(req.url, file=sys.stderr)
        res = req.get()
        for r in res.resources:
            yield r
        if res.next_url is None:
            break
        req.set_url(res.next_url)


def new_cloud_controller(config):
    """Configures the given config, and creates a new CloudController instance

    Args:
        config (Config)

    Returns:
        CloudController: a new instance"""
    return CloudController(configure(config))


def get_space_by_name(config, org_name, space_name):
    """This is a shortcut to create a new ``Space`` object. The space is looked
    up and initialized by org and space name.

    Args:
        config (Config)
        org_name (str)
        space_name (str)

    Returns:
        Space"""
    cc = new_cloud_controller(config)
    return Space(cc).init_by_name(org_name, space_name)


def get_space_by_guid(config, space_guid):
    """This is a shortcut to create a new ``Space`` object. The space is looked
    up and initialized by space guid.

    Args:
        config (Config)
        org_name (str)
        space_name (str)

    Returns:
        Space"""
    cc = new_cloud_controller(config)
    return Space(cc).init_by_guid(space_guid)


def main(argv, config):
    args = argparse.ArgumentParser()
    args.add_argument('-X', dest='method', default='GET')
    args.add_argument('-d', dest='body', action='store_true')
    args.add_argument('-l', dest='list', action='store_true')
    args.add_argument('-v', dest='verbose', action='store_true')
    args.add_argument('--short', action='store_true')
    args.add_argument('url')
    args = args.parse_args(argv)
    cc = new_cloud_controller(config)
    req = cc.request(args.url)
    if args.body:
        req.body = sys.stdin.read().encode('utf-8')
    if args.list:
        res = iterate_all_resources(req, args.verbose)
    else:
        res = req.send(args.method).resources
    if args.short:
        for item in res:
            print(item)
    else:
        json.dump(list(res), sys.stdout, indent=2, default=lambda o: o.data)


if __name__ == '__main__':
    main(sys.argv[1:], Config())
