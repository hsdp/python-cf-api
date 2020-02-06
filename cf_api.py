#!/usr/bin/env python3
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


def is_expired(jwt, now):
    parts = jwt.split('.', 2)
    if len(parts) != 3:
        raise RequestException('JWT is invalid: {}'.format(jwt))
    # add extra padding (==) to avoid b64decode errors
    data = b64decode((parts[1] + '==')).decode('utf-8')
    data = json.loads(data)
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

    """The API base url; read from environment var CF_URL"""
    base_url = os.getenv('CF_URL')

    """The API version; read from environment var CF_VERSION; defaults to v2"""
    version = os.getenv('CF_VERSION', 'v2')

    """The API username; read from environment var CF_USERNAME"""
    username = os.getenv('CF_USERNAME')

    """The API password; read from environment var CF_PASSWORD"""
    password = os.getenv('CF_PASSWORD')

    """The API client ID; read from environment var CF_CLIENT_ID;
    defaults to 'cf'"""
    client_id = os.getenv('CF_CLIENT_ID', 'cf')

    """The API client secret; read from environment var CF_CLIENT_SECRET;
    defaults to ''"""
    client_secret = os.getenv('CF_CLIENT_SECRET', '')

    """Indicates whether to attempt to automatically refresh the API
    access_token"""
    auto_refresh_token = os.getenv('CF_AUTO_REFRESH_TOKEN', 'true') != 'false'

    request_class = None

    info = None
    auth = None

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
        return self.data.get(name)

    def __repr__(self):
        """Shows the guid and name/host/label of this object"""
        name = str(self.host or self.label or self.name)
        return '\t'.join([self.guid, name])

    def __getattr__(self, name):
        """Accesses the .data dictionary key of `name\'"""
        return self.get(name)

    def __getitem__(self, name):
        """Accesses the .data dictionary key of `name\'"""
        return self.get(name)

    def __contains__(self, name):
        """Checks if .data contains `name\'"""
        return name in self.data


class V2Resource(Resource):
    """V2Resource wraps a v2 API object."""

    def get(self, name):
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
    """V3Resource wraps a v3 API object.
    """

    def get(self, name):
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

    """Indicates the *Resource wrapper class that should be used to wrap
    individual API resources
    """
    resource_class = Resource

    """Holds underlying requests.Response object"""
    response = None

    """Holds a JSON parsed dictionary of response content"""
    data = None

    def __init__(self, response):
        self.response = response
        self.data = json.loads(response.content)

    @property
    def next_url(self):
        raise ConfigException('Response.next_url not implemented.')

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
                raise ResponseException('Resource not found.')
        else:
            return self.resource_class(self.data)


class V2Response(Response):
    """V2Response wraps a v2 API response, providing access to the `next_url\'
    attr and error checks."""

    """Indicates the V2Resource wrapper class that should be used to wrap
    individual API resources.
    """
    resource_class = V2Resource

    @property
    def next_url(self):
        """Access the `next_url\' attribute from the response object"""
        return self.data.get('next_url', None)

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

    """Indicates the V3Resource wrapper class that should be used to wrap
    individual API resources"""
    resource_class = V3Resource

    @property
    def next_url(self):
        """Access the `pagination.next.href\' attribute from the response
        object"""
        if 'pagination' in self.data and \
                'next' in self.data['pagination'] and \
                self.data['pagination']['next'] is not None and \
                'href' in self.data['pagination']['next']:
            return self.data['pagination']['next']['href']
        return None

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

    """Indicates *Response class that should be used to wrap API responses
    received."""
    response_class = Response

    """Indicates the API config"""
    config = None

    """Indicates the HTTP body; must be bytes encoded"""
    body = None

    """Indicates the HTTP endpoint to request; use ``set_url()`` to control
    this value"""
    url = None

    version = None

    def __init__(self, config, *path, **query):
        self.config = config
        self.headers = {}
        if self.version is None:
            self.version = config.version
        self.set_url(*path, **query)

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

    def send(self, method):
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

    """The config for this client"""
    config = None

    def __init__(self, config):
        self.config = config

    @property
    def request_class(self):
        """Picks the correct *Request wrapper class based on
        config.request_class (if set) otherwise
        config.version (i.e. V2Request for ``v2\' or V3Request for ``v3\')"""
        if self.config.request_class is not None:
            return self.config.request_class
        return getattr(sys.modules[__name__],
                       self.config.version.upper() + 'Request')

    def v2(self, *path, **query):
        """Creates an instance of V2Request

        Args:
            *path (str): a list of URL path segments
            **query (dict): a dict of query string pairs

        Returns:
            V2Request"""
        return V2Request(self.config, *path, **query)

    def v3(self, *path, **query):
        """Creates an instance of V3Request

        Args:
            *path (str): a list of URL path segments
            **query (dict): a dict of query string pairs

        Returns:
            V3Request"""
        return V3Request(self.config, *path, **query)

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

    """CloudController instance"""
    cc = None

    """Resource object representing the organization"""
    org = None

    """Resource object representing the space"""
    space = None

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
