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
import sys
import json
import time
import cf_api
import requests
import responses as r
from base64 import b64encode
from unittest import TestCase


def jwt_payload(jwt_data):
    return b64encode(json.dumps(jwt_data).encode('utf-8')).decode('utf-8')


def jwt_token(jwt_payload):
    return '<JWTDETAILS>.{}.<SIGNATURE>'.format(jwt_payload)


cf_url = 'http://localhost:8080'
uaa_url = 'http://localhost:8081'
cf_username = 'usr'
cf_password = '***'
test_org_guid = 'org-guid-1'
test_org_name = 'org-1'
test_space_guid = 'space-guid-1'
test_space_name = 'space-1'
test_jwt_data = {"client_id": "cf", "iat": 1572026076, "exp": 1572026676}
test_jwt_token = jwt_token(jwt_payload(test_jwt_data))
test_jwt_token_live = jwt_token(jwt_payload({'exp': int(time.time()) + 3600}))
test_config_info = {'token_endpoint': uaa_url}
test_config_auth = {'access_token': test_jwt_token_live,
                    'refresh_token': test_jwt_token_live}
test_org_v2 = {'metadata': {'guid': test_org_guid},
               'entity': {'name': test_org_name}}
test_space_v2 = {'metadata': {'guid': test_space_guid},
                 'entity': {'name': test_space_name,
                            'organization_guid': test_org_guid,
                            'organization_url': '/'.join([
                                '', 'v2', 'organizations', test_org_guid]),
                            'random_key': 'random_value'}}
test_error_v2 = {'error_code': 'CF-Error'}
test_org_v3 = {'guid': test_org_guid, 'name': test_org_name}
test_space_v3 = {'guid': test_space_guid, 'name': test_space_name,
                 'relationships': {
                     'organization': {'data': {'guid': test_org_guid}}},
                 'links': {'organization': {'href': '/'.join([
                     cf_url, 'v3', 'organizations', test_org_guid])}}}
test_error_v3 = {'errors': [{'title': 'CF-Error', 'detail': 'test error'}]}


def new_config(version='v2', username=cf_username, password=cf_password,
               with_auth=False, with_info=False):
    config = cf_api.Config()
    config.base_url = cf_url
    config.username = username
    config.password = password
    config.version = version
    if with_auth:
        config.auth = test_config_auth
    if with_info:
        config.info = test_config_info
    return config


def get_response(data, response_class=cf_api.Response):
    res = requests.Response()
    res._content = json.dumps(data).encode('utf-8')
    return response_class(res)


def add_info(status=200):
    r.add(r.GET, cf_url + '/v2/info', status=status,
          json=test_config_info)


def add_auth(status=200):
    r.add(r.POST, uaa_url + '/oauth/token', status=status,
          json=test_config_auth)


def add_org_space_v2(status=200):
    r.add(r.GET, '/'.join([cf_url, 'v2', 'organizations']),
          status=status, json={'resources': [test_org_v2]})
    r.add(r.GET, '/'.join([cf_url, 'v2', 'organizations',
                           test_org_guid, 'spaces']),
          status=status, json={'resources': [test_space_v2]})
    r.add(r.GET, '/'.join([cf_url, 'v2', 'spaces', test_space_guid]),
          status=status, json=test_space_v2)
    r.add(r.GET, '/'.join([cf_url, 'v2', 'organizations', test_org_guid]),
          status=status, json=test_org_v2)


def add_org_space_v3(status=200):
    r.add(r.GET, '/'.join([cf_url, 'v3', 'organizations']),
          status=status, json={'resources': [test_org_v3]})
    r.add(r.GET, '/'.join([cf_url, 'v3', 'organizations', test_org_guid]),
          status=status, json=test_org_v3)
    r.add(r.GET, '/'.join([cf_url, 'v3', 'spaces']),
          status=status, json={'resources': [test_space_v3]})
    r.add(r.GET, '/'.join([cf_url, 'v3', 'spaces', test_space_guid]),
          status=status, json=test_space_v3)


class TestIsExpired(TestCase):
    def test_true(self):
        token = jwt_token(jwt_payload(test_jwt_data))
        self.assertTrue(cf_api.is_expired(token, time.time()))

    def test_false(self):
        token = jwt_token(jwt_payload(test_jwt_data))
        self.assertFalse(cf_api.is_expired(token, test_jwt_data['exp'] - 1))

    def test_invalid_jwt(self):
        with self.assertRaises(cf_api.RequestException) as ctx:
            cf_api.jwt_decode('')
        self.assertIn('invalid', str(ctx.exception))

    def test_expiration_not_found(self):
        with self.assertRaises(cf_api.RequestException) as ctx:
            cf_api.is_expired(jwt_token(jwt_payload({})), time.time())
        self.assertIn('not found', str(ctx.exception))


class TestConfigure(TestCase):
    @r.activate
    def test_success(self):
        config = new_config()
        add_info()
        cf_api.configure(config)
        self.assertFalse(config.info is None)

    @r.activate
    def test_failed(self):
        config = new_config()
        add_info(status=404)
        with self.assertRaises(cf_api.ResponseException) as ctx:
            cf_api.configure(config)
        self.assertIn('Error configuring', str(ctx.exception))


class TestBuildAuthenticationRequest(TestCase):
    def test_grant_type_password(self):
        config = new_config()
        req = cf_api.build_authentication_request(config)
        parts = [
            ('grant_type', 'password'),
            ('username', config.username),
            ('password', config.password),
            ('client_id', 'cf'),
            ('client_secret', ''),
        ]
        self.assertEqual(len(req), len(parts))
        for name, value in parts:
            self.assertIn(name, req)
            self.assertEqual(req[name], value)

    def test_grant_type_password_failed(self):
        config = new_config()
        config.auth = {}
        with self.assertRaises(cf_api.RequestException) as ctx:
            cf_api.build_authentication_request(config)
        self.assertIn('Unable to build authentication', str(ctx.exception))

    def test_grant_type_refresh_token(self):
        config = new_config(with_auth=True)
        req = cf_api.build_authentication_request(config)
        parts = [
            ('grant_type', 'refresh_token'),
            ('client_id', 'cf'),
            ('client_secret', ''),
            ('refresh_token', config.auth['refresh_token'])
        ]
        self.assertEqual(len(req), len(parts))
        for name, value in parts:
            self.assertIn(name, req)
            self.assertEqual(req[name], value)

    def test_grant_type_client_credentials(self):
        config = new_config(username=None, password=None)
        req = cf_api.build_authentication_request(config)
        parts = [
            ('grant_type', 'client_credentials'),
            ('client_id', 'cf'),
            ('client_secret', ''),
        ]
        self.assertEqual(len(req), len(parts))
        for name, value in parts:
            self.assertIn(name, req)
            self.assertEqual(req[name], value)


class TestAuthenticate(TestCase):
    @r.activate
    def test_success(self):
        add_auth()
        config = new_config(with_info=True)
        req = cf_api.build_authentication_request(config)
        self.assertTrue(config.auth is None)
        cf_api.authenticate(config, req)
        self.assertFalse(config.auth is None)

    def test_failed_config_info(self):
        config = new_config()
        req = cf_api.build_authentication_request(config)
        self.assertTrue(config.auth is None)
        with self.assertRaises(cf_api.ConfigException) as ctx:
            cf_api.authenticate(config, req)
        self.assertIn('Config info is required', str(ctx.exception))

    @r.activate
    def test_failed_config_auth(self):
        add_info()
        add_auth()
        config = new_config(with_info=True)
        config.auto_refresh_token = False
        cc = cf_api.new_cloud_controller(config)
        with self.assertRaises(cf_api.ConfigException) as ctx:
            cc.request('apps').get()
        self.assertIn('Config auth is required', str(ctx.exception))

    @r.activate
    def test_failed_response_exception(self):
        add_auth(status=404)
        config = new_config(with_info=True)
        req = cf_api.build_authentication_request(config)
        self.assertTrue(config.auth is None)
        with self.assertRaises(cf_api.ResponseException) as ctx:
            cf_api.authenticate(config, req)
        self.assertIn('Error authenticating', str(ctx.exception))


class TestResource(TestCase):

    def test_getattr_getitem(self):
        res = cf_api.V2Resource(test_space_v2)
        self.assertEqual(res['entity']['random_key'],
                         test_space_v2['entity']['random_key'])
        self.assertEqual(res.entity['random_key'],
                         test_space_v2['entity']['random_key'])

    def test_contains(self):
        res = cf_api.V2Resource(test_space_v2)
        self.assertIn('metadata', res)

    def test_repr(self):
        res = cf_api.V2Resource(test_space_v2)
        self.assertEqual(str(res), '\t'.join([res.guid, res.name]))

    def test_get(self):
        res = cf_api.V2Resource(test_space_v2)
        self.assertEqual(test_space_v2['metadata']['guid'], res.guid)


class TestV2Resource(TestCase):

    def test_get(self):
        res = cf_api.V2Resource(test_space_v2)
        self.assertEqual(res.guid, test_space_v2['metadata']['guid'])
        self.assertEqual(res.name, test_space_v2['entity']['name'])
        self.assertEqual(res.organization_url,
                         test_space_v2['entity']['organization_url'])
        self.assertIsNone(res.nonexistent_url)
        self.assertEqual(res.organization_guid,
                         test_space_v2['entity']['organization_guid'])
        self.assertIsNone(res.nonexistent_guid)
        self.assertIsNone(res.nonexistent_key)
        self.assertEqual(res.metadata, test_space_v2['metadata'])
        self.assertEqual(res.entity, test_space_v2['entity'])


class TestV3Resource(TestCase):

    def test_get(self):
        res = cf_api.V3Resource(test_space_v3)
        org_guid = \
            test_space_v3['relationships']['organization']['data']['guid']
        self.assertEqual(res.guid, test_space_v3['guid'])
        self.assertEqual(res.name, test_space_v3['name'])
        self.assertEqual(res.organization_url,
                         test_space_v3['links']['organization']['href'])
        self.assertEqual(res.organization_guid,
                         org_guid)
        self.assertIsNone(res.nonexistent_key)
        res = cf_api.V3Resource({})
        self.assertIsNone(res.nonexistent_url)
        self.assertIsNone(res.nonexistent_guid)
        res = cf_api.V3Resource({'links': {}, 'relationships': {}})
        self.assertIsNone(res.nonexistent_url)
        self.assertIsNone(res.nonexistent_guid)


class TestResponse(TestCase):

    def test_dir(self):
        dir(get_response({}))

    def test_assert_ok(self):
        # This test exists mainly to improve code coverage :P
        with self.assertRaises(cf_api.ConfigException):
            get_response({}).assert_ok()

    @r.activate
    def test_resources_attr_with_single_resource(self):
        add_info()
        add_auth()
        r.add(r.GET, cf_url + '/v2/spaces/' + test_space_guid, status=200,
              json=test_space_v2)
        config = new_config()
        cc = cf_api.new_cloud_controller(config)
        res = cc.request('spaces', test_space_guid).get()
        self.assertEqual(res.resources[0].guid, test_space_guid)

    @r.activate
    def test_resource_attr_with_multiple_resources(self):
        add_info()
        add_auth()
        r.add(r.GET, cf_url + '/v2/spaces', status=200,
              json={'resources': [test_space_v2]})
        config = new_config()
        cc = cf_api.new_cloud_controller(config)
        res = cc.request('spaces').get()
        self.assertEqual(res.resource.guid, test_space_guid)

    @r.activate
    def test_resource_with_empty_resources(self):
        add_info()
        add_auth()
        r.add(r.GET, cf_url + '/v2/spaces', status=200,
              json={'resources': []})
        config = new_config()
        cc = cf_api.new_cloud_controller(config)
        res = cc.request('spaces').get()
        with self.assertRaises(cf_api.ResponseException) as ctx:
            res.resource
        self.assertIn('Resource not found', str(ctx.exception))


class TestV2Response(TestCase):
    @r.activate
    def test_next_url(self):
        add_info()
        add_auth()
        r.add(r.GET, cf_url + '/v2/spaces', status=200,
              json={'resources': [test_space_v2], 'next_url': '/next'})
        config = new_config()
        cc = cf_api.new_cloud_controller(config)
        res = cc.request('spaces').get()
        self.assertEqual(res.next_url, '/next')

    @r.activate
    def test_assert_ok(self):
        add_info()
        add_auth()
        r.add(r.GET, cf_url + '/v2/spaces', status=400, json=test_error_v2)
        config = new_config(version='v2')
        cc = cf_api.new_cloud_controller(config)
        res = cc.request('spaces').get()
        with self.assertRaises(cf_api.ResponseException):
            res.assert_ok()
        r.add(r.GET, cf_url + '/v2/organizations', status=400, json={})
        res = cc.request('organizations').get()
        with self.assertRaises(cf_api.ResponseException):
            res.assert_ok()


class TestV3Response(TestCase):

    def test_getattr(self):
        res = get_response({
            'pagination': {
                'next': {
                    'href': cf_url + '/v3/spaces/' + test_space_guid
                },
                'total_pages': 1,
                'total_results': 1,
            },
        }, cf_api.V3Response)
        self.assertEqual(res.next_url, res.data['pagination']['next']['href'])
        self.assertEqual(res.total_pages, 1)
        self.assertEqual(res.total_results, 1)
        self.assertIsNone(res.nonexistent_key)

    @r.activate
    def test_next_url(self):
        add_info()
        add_auth()
        r.add(r.GET, cf_url + '/v3/spaces', status=200,
              json={'resources': [test_space_v3]})
        config = new_config(version='v3')
        cc = cf_api.new_cloud_controller(config)
        res = cc.request('spaces').get()
        self.assertIsNone(res.next_url)

    @r.activate
    def test_assert_ok(self):
        add_info()
        add_auth()
        r.add(r.GET, cf_url + '/v3/spaces', status=400, json=test_error_v3)
        config = new_config(version='v3')
        cc = cf_api.new_cloud_controller(config)
        res = cc.request('spaces').get()
        with self.assertRaises(cf_api.ResponseException):
            res.assert_ok()
        r.add(r.GET, cf_url + '/v3/organizations', status=400, json={})
        res = cc.request('organizations').get()
        with self.assertRaises(cf_api.ResponseException):
            res.assert_ok()


class TestRequest(TestCase):
    def setUp(self):
        self.config = new_config(with_auth=True, with_info=True)
        self.req = cf_api.Request(self.config, 'apps')

    def test_dir(self):
        dir(self.req)

    def test_getattr(self):
        self.assertEqual(self.req.spaces.url, cf_url + '/v2/apps/spaces')

    def test_set_query(self):
        self.assertEqual(self.req.set_query(page=1).url,
                         cf_url + '/v2/apps?page=1')

    def test_init(self):
        self.assertEqual(self.req.url, cf_url + '/v2/apps')

    def test_set_url(self):
        self.req.set_url('apps?page=2')
        self.assertEqual(self.req.url, cf_url + '/v2/apps?page=2')

    def test_set_url_kwargs(self):
        self.req.set_url('apps', page=3)
        self.assertEqual(self.req.url, cf_url + '/v2/apps?page=3')

    def test_set_url_clean_prefix(self):
        self.req.set_url('/v2/apps')
        self.assertEqual(self.req.url, cf_url + '/v2/apps')

    def test_set_url_clean_base(self):
        self.req.set_url(cf_url + '/v2/apps')
        self.assertEqual(self.req.url, cf_url + '/v2/apps')

    def test_set_body(self):
        self.req.set_body({'instances': 1})
        self.assertEqual(self.req.body, b'{"instances": 1}')

    @r.activate
    def test_send_retry(self):
        self.num_req = 0

        def space_callback(req):
            if self.num_req == 0:
                res = (200, {}, json.dumps(test_space_v2))
            elif self.num_req == 1:
                res = (401, {}, json.dumps({}))
            elif self.num_req == 2:
                res = (200, {}, json.dumps(test_space_v2))
            else:
                raise Exception('Why am I here?')
            self.num_req += 1
            return res

        add_info()
        add_auth()
        r.add_callback(r.GET, cf_url + '/v2/spaces/' + test_space_guid,
                       callback=space_callback,
                       content_type='application/json')
        # should succeed
        res = cf_api.Request(self.config, 'spaces', test_space_guid).get()
        self.assertTrue(res.ok)
        # should get 401 and retry and succeed
        res = cf_api.Request(self.config, 'spaces', test_space_guid).get()
        self.assertTrue(res.ok)
        # check that we num_req is as expected
        self.assertEqual(self.num_req, 3)
        # check that we got the calls we expected
        expected = [
            cf_url + '/v2/spaces/' + test_space_guid,
            cf_url + '/v2/spaces/' + test_space_guid,
            cf_url + '/v2/info',
            uaa_url + '/oauth/token',
            cf_url + '/v2/spaces/' + test_space_guid,
        ]
        for i, url in enumerate(expected):
            self.assertEqual(r.calls[i].request.url, url)

    @r.activate
    def test_send_get(self):
        r.add(r.GET, cf_url + '/v2/spaces/' + test_space_guid, status=200,
              json=test_space_v2)
        res = cf_api.Request(self.config, 'spaces', test_space_guid).get()
        self.assertIsInstance(res, cf_api.Response)

    @r.activate
    def test_send_post(self):
        r.add(r.POST, cf_url + '/v2/spaces/' + test_space_guid, status=200,
              json=test_space_v2)
        res = cf_api.Request(self.config, 'spaces', test_space_guid).post()
        self.assertIsInstance(res, cf_api.Response)

    @r.activate
    def test_send_put(self):
        r.add(r.PUT, cf_url + '/v2/spaces/' + test_space_guid, status=200,
              json=test_space_v2)
        res = cf_api.Request(self.config, 'spaces', test_space_guid).put()
        self.assertIsInstance(res, cf_api.Response)

    @r.activate
    def test_send_delete(self):
        r.add(r.DELETE, cf_url + '/v2/spaces/' + test_space_guid, status=200,
              json=test_space_v2)
        res = cf_api.Request(self.config, 'spaces', test_space_guid).delete()
        self.assertIsInstance(res, cf_api.Response)


class TestIterateAllResources(TestCase):
    @r.activate
    def test_iterate_all_resources(self):
        r.add(r.Response(method=r.GET, url=cf_url + '/v3/apps',
              status=200, json={
                  'pagination': {'next': {'href': cf_url + '/v3/apps?page=2'}},
                  'resources': [{'guid': 'abc'}],
              }, match_querystring=True))
        r.add(r.Response(method=r.GET, url=cf_url + '/v3/apps?page=2',
              status=200, json={
                  'pagination': {'next': {'href': None}},
                  'resources': [{'guid': 'def'}],
              }, match_querystring=True))
        config = new_config(version='v3', with_auth=True, with_info=True)
        req = cf_api.V3Request(config, '/v3/apps')
        res = list(cf_api.iterate_all_resources(req))
        self.assertEqual(len(res), 2)
        self.assertEqual(res[0].guid, 'abc')
        self.assertEqual(res[1].guid, 'def')


class TestCloudController(TestCase):
    @r.activate
    def test_new_cloud_controller_v2(self):
        add_info()
        config = new_config(version='v2')
        cc = cf_api.new_cloud_controller(config)
        self.assertEqual(cc.request_class, cf_api.V2Request)

    @r.activate
    def test_new_cloud_controller_v3(self):
        add_info()
        config = new_config(version='v3')
        cc = cf_api.new_cloud_controller(config)
        self.assertEqual(cc.request_class, cf_api.V3Request)

    @r.activate
    def test_getattr(self):
        add_info()
        config = new_config(version='v3', with_info=True)
        cc = cf_api.new_cloud_controller(config)
        self.assertIsInstance(cc.apps, cf_api.V3Request)

    @r.activate
    def test_v2(self):
        add_info()
        add_auth()
        r.add(method=r.GET, url=cf_url + '/v2/spaces', status=200,
              json={'resources': [test_space_v2]})
        config = new_config(version='v3')
        cc = cf_api.new_cloud_controller(config)
        req = cc.v2('spaces')
        self.assertIsInstance(req, cf_api.V2Request)
        res = req.get()
        self.assertIsInstance(res, cf_api.V2Response)

    @r.activate
    def test_v3(self):
        add_info()
        add_auth()
        r.add(method=r.GET, url=cf_url + '/v3/spaces', status=200,
              json={'resources': [test_space_v3]})
        config = new_config(version='v2')
        cc = cf_api.new_cloud_controller(config)
        req = cc.v3('spaces')
        self.assertIsInstance(req, cf_api.V3Request)
        res = req.get()
        self.assertIsInstance(res, cf_api.V3Response)

    @r.activate
    def test_request(self):
        add_info()
        config = new_config(version='v3')
        cc = cf_api.new_cloud_controller(config)
        req = cc.request('apps')
        self.assertEqual(req.url, cf_url + '/v3/apps')

    @r.activate
    def test_request_custom_class(self):

        class MyRequest(cf_api.V3Request):
            pass

        add_info()
        config = new_config(version='v3')
        config.request_class = MyRequest
        cc = cf_api.new_cloud_controller(config)
        req = cc.request('apps')
        self.assertIsInstance(req, MyRequest)

    @r.activate
    def test_get_space_by_name_v2(self):
        add_info()
        add_auth()
        add_org_space_v2()
        config = new_config(version='v2')
        cc = cf_api.new_cloud_controller(config)
        org, space = cc.get_space_by_name(test_org_name, test_space_name)
        self.assertEqual(org.name, test_org_name)
        self.assertEqual(space.name, test_space_name)

    @r.activate
    def test_get_space_by_name_v3(self):
        add_info()
        add_auth()
        add_org_space_v3()
        config = new_config(version='v3')
        cc = cf_api.new_cloud_controller(config)
        org, space = cc.get_space_by_name(test_org_name, test_space_name)
        self.assertEqual(org.name, test_org_name)
        self.assertEqual(space.name, test_space_name)

    @r.activate
    def test_get_space_by_guid(self):
        add_info()
        add_auth()
        add_org_space_v2()
        config = new_config(version='v2')
        cc = cf_api.new_cloud_controller(config)
        org, space = cc.get_space_by_guid(test_space_guid)
        self.assertEqual(org.guid, test_org_guid)
        self.assertEqual(space.guid, test_space_guid)


class TestSpace(TestCase):
    @r.activate
    def test_request_v2(self):
        add_info()
        add_auth()
        add_org_space_v2()
        config = new_config(version='v2')
        space = cf_api.get_space_by_name(
            config, test_org_name, test_space_name)
        req = space.request('apps', **{'results-per-page': 1})
        exp_url = cf_url + '/v2/apps?q=space_guid%3A' + \
            test_space_guid + '&results-per-page=1'
        self.assertEqual(req.url, exp_url)

    @r.activate
    def test_request_v3(self):
        add_info()
        add_auth()
        add_org_space_v3()
        config = new_config(version='v3')
        space = cf_api.get_space_by_guid(config, test_space_guid)
        req = space.request('apps', per_page=1)
        if sys.version_info[0] == 2:
            exp_url = cf_url + '/v3/apps?per_page=1&space_guids=' + \
                test_space_guid
        else:
            exp_url = cf_url + '/v3/apps?space_guids=' + \
                test_space_guid + '&per_page=1'
        self.assertEqual(req.url, exp_url)


class TestMain(TestCase):
    @r.activate
    def test_main_flags(self):
        add_info()
        add_auth()
        r.add(method=r.GET, url=cf_url + '/v2/spaces', status=200,
              json={'resources': [test_space_v2]})
        config = new_config()
        cf_api.main(['-X', 'POST', '-v', '-l', '--short', 'spaces'], config)

    @r.activate
    def test_main_noflags(self):
        add_info()
        add_auth()
        r.add(method=r.GET, url=cf_url + '/v2/spaces', status=200,
              json={'resources': [test_space_v2]})
        config = new_config()
        cf_api.main(['spaces'], config)
