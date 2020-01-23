import six
import time
import json
import responses
import cf_api
import functools
from mock_cc import (prepare_request, cc_api_url, uaa_api_url, cc_v2_info,
                     uaa_oauth_token, make_uaa_oauth_token, make_response_list)
from unittest import TestCase
from uuid import uuid4


def setup_request(method, endpoint, guid1=None, relation=None, guid2=None, **kwargs):

    def decorator(func):

        @responses.activate
        def wrap(self):
            req = prepare_request(self.cc, method, endpoint, guid1, relation, guid2, **kwargs)
            return func(self, req)

        return wrap

    return decorator


class CloudControllerRequest(TestCase):
    def setUp(self):
        self.cc = cf_api.CloudController(cc_api_url)

    @setup_request('GET', 'apps')
    def test_search(self, req):
        res = req.search('name', 'foo')
        self.assertIsInstance(res, cf_api.CloudControllerResponse)
        self.assertIsInstance(res.resources, list)
        self.assertListEqual(req.query, [('q', 'name:foo')])

    @setup_request('GET', 'apps')
    def test_get_by_name(self, req):
        res = req.get_by_name('foo')
        self.assertIsInstance(res, cf_api.CloudControllerResponse)
        self.assertIsInstance(res.resources, list)
        self.assertListEqual(req.query, [('q', 'name:foo')])
        res = req.get_by_name('bar', 'label')
        self.assertIsInstance(res, cf_api.CloudControllerResponse)
        self.assertIsInstance(res.resources, list)
        self.assertListEqual(req.query, [('q', 'label:bar')])


class V3CloudControllerResponse(TestCase):
    def setUp(self):
        self.cc = cf_api.CloudController(cc_api_url).v3

    @setup_request('GET', 'apps', status=400, version=3)
    def test_error_message(self, req):
        res = req.get()
        self.assertIsInstance(res, cf_api.V3CloudControllerResponse)
        self.assertIsInstance(res.error_message[0], six.string_types)
        self.assertEqual(res.error_message[0],
                         'CF-ErrorCode: an error occurred (400)')

    @setup_request('GET', 'apps', status=400, version=3)
    def test_error_code(self, req):
        res = req.get()
        self.assertIsInstance(res, cf_api.V3CloudControllerResponse)
        self.assertIsInstance(res.error_code[0], six.string_types)
        self.assertEqual(res.error_code[0], '400')

    @setup_request('GET', 'apps', version=3)
    def test_resource(self, req):
        res = req.get()
        self.assertIsInstance(res.resource, cf_api.V3Resource)

    @setup_request('GET', 'apps', version=3, n=2)
    def test_resources(self, req):
        res = req.get()
        self.assertIsInstance(res.resources, list)
        self.assertEqual(len(res.resources), 2)
        self.assertIsInstance(res.resources[0], cf_api.V3Resource)

    @setup_request('GET', 'apps', version=3, next_url_path='v3/apps?page=2')
    def test_next_url(self, req):
        res = req.get()
        next_url = cc_api_url + '/v3/apps?page=2'
        self.assertEqual(res.next_url, next_url)


class CloudControllerResponse(TestCase):
    def setUp(self):
        self.cc = cf_api.CloudController(cc_api_url)

    @setup_request('GET', 'apps', status=400)
    def test_error_message(self, req):
        res = req.search('name', 'foo')
        self.assertIsInstance(res, cf_api.CloudControllerResponse)
        self.assertIsInstance(res.error_message, six.string_types)

    @setup_request('GET', 'apps', status=400)
    def test_error_code(self, req):
        res = req.search('name', 'foo')
        self.assertIsInstance(res, cf_api.CloudControllerResponse)
        self.assertIsInstance(res.error_code, six.string_types)
        self.assertEqual(res.error_code, '400')

    @setup_request('GET', 'apps')
    def test_resources(self, req):
        res = req.search('name', 'foo')
        self.assertIsInstance(res, cf_api.CloudControllerResponse)
        self.assertIsInstance(res.resources, list)
        self.assertIsInstance(res.resource, cf_api.Resource)

    @setup_request('GET', 'apps')
    def test_first_of_many_resources(self, req):
        res = req.search('name', 'foo')
        self.assertIsInstance(res, cf_api.CloudControllerResponse)
        self.assertIsInstance(res.resources, list)
        self.assertIsInstance(res.resource, cf_api.Resource)

    @setup_request('GET', 'apps', 'guid')
    def test_first_of_many_resources(self, req):
        res = req.search('name', 'foo')
        self.assertIsInstance(res, cf_api.CloudControllerResponse)
        self.assertIsInstance(res.resource, cf_api.Resource)


class Resource(TestCase):
    def setUp(self):
        self.cc = cf_api.CloudController(cc_api_url)

    @setup_request('GET', 'apps')
    def test_guid(self, req):
        res = req.get()
        self.assertIsInstance(res, cf_api.CloudControllerResponse)
        self.assertIsInstance(res.resource.guid, six.string_types)

    @setup_request('GET', 'apps')
    def test_name(self, req):
        res = req.get()
        self.assertIsInstance(res, cf_api.CloudControllerResponse)
        self.assertIsInstance(res.resource.name, six.string_types)

    @setup_request('GET', 'apps')
    def test_label(self, req):
        res = req.get()
        self.assertIsInstance(res, cf_api.CloudControllerResponse)
        self.assertIsInstance(res.resource.label, six.string_types)

    @setup_request('GET', 'apps')
    def test_status(self, req):
        res = req.get()
        self.assertIsInstance(res, cf_api.CloudControllerResponse)
        self.assertIsInstance(res.resource.status, six.string_types)


class V3Resource(TestCase):
    def setUp(self):
        self.cc = cf_api.CloudController(cc_api_url).v3

    @setup_request('GET', 'apps', version=3)
    def test_guid(self, req):
        res = req.get()
        self.assertIsInstance(res.resource.guid, six.string_types)

    @setup_request('GET', 'apps', version=3)
    def test_name(self, req):
        res = req.get()
        self.assertIsInstance(res.resource.name, six.string_types)

    @setup_request('GET', 'apps', version=3)
    def test_space_guid(self, req):
        res = req.get()
        self.assertEqual(res.resource.space_guid, res.resource.guid)

    @setup_request('GET', 'spaces', version=3)
    def test_org_guid(self, req):
        res = req.get()
        self.assertEqual(res.resource.org_guid, res.resource.guid)

    @setup_request('GET', 'apps', version=3)
    def test_href(self, req):
        res = req.get()
        href = '/'.join([cc_api_url, 'v3/apps', res.resource.guid])
        self.assertEqual(res.resource.href, href)

    @setup_request('GET', 'spaces', version=3)
    def test_org_guid(self, req):
        res = req.get()
        href = '/'.join([cc_api_url, 'v3/organizations', res.resource.guid])
        self.assertEqual(res.resource.organization_url, href)

    @setup_request('GET', 'apps', version=3)
    def test_state(self, req):
        res = req.get()
        self.assertEqual(res.resource.state, 'STARTED')


class NewUAA(TestCase):
    def setUp(self):
        prepare_request(cc_api_url, 'GET', 'info', body=cc_v2_info)
        prepare_request(uaa_api_url, 'POST', 'oauth/token', body=uaa_oauth_token, version=None)

    @responses.activate
    def test_oauth_client_credentials_grant(self):
        cf_api.new_uaa(
            cc_api_url,
            client_id='abc',
            client_secret='',
        )

    @responses.activate
    def test_oauth_password_grant(self):
        cf_api.new_uaa(
            cc_api_url,
            client_id='abc',
            client_secret='',
            username='foo',
            password='bar',
        )

    @responses.activate
    def test_oauth_refresh_token(self):
        cf_api.new_uaa(
            cc_api_url,
            client_id='abc',
            client_secret='',
            refresh_token=uaa_oauth_token['refresh_token'],
        )

    @responses.activate
    def test_oauth_access_token(self):
        cf_api.new_uaa(
            cc_api_url,
            client_id='abc',
            client_secret='',
            access_token=uaa_oauth_token['refresh_token'],
        )

    @responses.activate
    def test_no_auth(self):
        uaa = cf_api.new_uaa(
            cc_api_url,
            client_id='abc',
            client_secret='',
            no_auth=True,
        )
        self.assertIsNone(uaa.get_access_token())
        self.assertIsNone(uaa.get_refresh_token())

    @responses.activate
    def test_oauth_authorization_code_url(self):
        uaa = cf_api.new_uaa(
            cc_api_url,
            client_id='abc',
            client_secret='',
            no_auth=True,
        )
        self.assertIsNone(uaa.get_access_token())
        self.assertIsNone(uaa.get_refresh_token())
        url = uaa.authorization_code_url('code', 'cloud_controller.read', '{0}/success'.format(cc_api_url))
        self.assertEqual(url, '{0}/oauth/authorize?response_type=code&client_id=abc&response_type=code&client_id=abc&scope=cloud_controller.read&redirect_uri=http%3A%2F%2Flocalhost%2Fsuccess'.format(cc_api_url))


class UAA(TestCase):
    def test_set_client_credentials_no_basic_auth(self):
        uaa = cf_api.UAA(cc_api_url)
        uaa.set_client_credentials('abc', '123')
        self.assertNotIn('authorization', uaa.headers)

    def test_set_client_credentials_basic_auth(self):
        uaa = cf_api.UAA(cc_api_url)
        uaa.set_client_credentials('abc', '123', set_basic_auth=True)
        self.assertIn('authorization', uaa.headers)
        self.assertEqual(uaa.get_header('authorization'), 'Basic YWJjOjEyMw==')


class NewCloudController(TestCase):
    def setUp(self):
        prepare_request(cc_api_url, 'GET', 'info', body=cc_v2_info)
        prepare_request(uaa_api_url, 'POST', 'oauth/token', body=uaa_oauth_token, version=None)

    @responses.activate
    def test_new_cloud_controller(self):
        cc = cf_api.new_cloud_controller(
            cc_api_url,
            client_id='abc',
            client_secret='',
            verify_ssl=False,
        )
        self.assertIsInstance(cc, cf_api.CloudController)
        self.assertIsInstance(cc.info, cf_api.CFInfo)
        self.assertIsInstance(cc.uaa, cf_api.UAA)
        self.assertFalse(cc.verify_ssl)
        self.assertFalse(cc.uaa.verify_ssl)

    @responses.activate
    def test_custom_cloud_controller(self):

        class MyCC(cf_api.CloudController):
            pass

        cc = cf_api.new_cloud_controller(
            cc_api_url,
            client_id='abc',
            client_secret='',
            verify_ssl=False,
            cloud_controller_class=MyCC,
        )
        self.assertIsInstance(cc, MyCC)
        self.assertIsInstance(cc.info, cf_api.CFInfo)
        self.assertIsInstance(cc.uaa, cf_api.UAA)
        self.assertFalse(cc.verify_ssl)
        self.assertFalse(cc.uaa.verify_ssl)

    @responses.activate
    def test_no_auth(self):
        cc = cf_api.new_cloud_controller(
            cc_api_url,
            client_id='abc',
            client_secret='',
            verify_ssl=False,
            no_auth=True,
        )
        self.assertIsNone(cc.uaa.get_access_token())
        self.assertIsNone(cc.uaa.get_refresh_token())


class RefreshTokens(TestCase):
    @responses.activate
    def test_refresh_tokens_callback(self):
        orig_token = make_uaa_oauth_token(2)
        refreshed_token = make_uaa_oauth_token(2)
        self.assertNotEqual(orig_token['access_token'], refreshed_token['access_token'])
        prepare_request(cc_api_url, 'GET', 'info', body=cc_v2_info)
        prepare_request(uaa_api_url, 'POST', 'oauth/token', body=orig_token, version=None)
        prepare_request(cc_api_url, 'GET', 'apps')
        prepare_request(uaa_api_url, 'POST', 'oauth/token', body=refreshed_token, version=None)
        prepare_request(cc_api_url, 'GET', 'apps')

        cc = cf_api.new_cloud_controller(
            cc_api_url,
            client_id='abc',
            client_secret='',
            verify_ssl=False,
        )
        cc.set_refresh_tokens_callback()
        app = cc.apps().get().resource
        self.assertIsInstance(app, cf_api.Resource)
        self.assertEqual(cc.uaa.get_access_token().to_string(),
                         orig_token['access_token'])
        time.sleep(2)
        app = cc.apps().get().resource
        self.assertIsInstance(app, cf_api.Resource)
        self.assertEqual(cc.uaa.get_access_token().to_string(),
                         refreshed_token['access_token'])


class CloudController(TestCase):
    def setUp(self):
        prepare_request(cc_api_url, 'GET', 'info',
                        body=cc_v2_info)
        prepare_request(uaa_api_url, 'POST', 'oauth/token',
                        body=uaa_oauth_token, version=None)

    @responses.activate
    def test_get_all_resources(self):
        prepare_request(cc_api_url, 'GET', 'apps',
                        body=make_response_list(2, 'apps', 1,
                                                next_url='apps'))
        prepare_request(cc_api_url, 'GET', 'apps',
                        body=make_response_list(2, 'apps', 1))

        cc = cf_api.new_cloud_controller(
            cc_api_url,
            client_id='abc',
            client_secret='',
            verify_ssl=False,
        )
        req = cc.apps()
        apps = cc.get_all_resources(req)
        self.assertIsInstance(apps, list)
        self.assertIsInstance(apps[0], cf_api.Resource)
        self.assertEqual(2, len(apps))

    @responses.activate
    def test_set_version(self):
        cc = cf_api.new_cloud_controller(
            cc_api_url,
            client_id='abc',
            client_secret='',
            verify_ssl=False,
        )
        cc.set_version(3)
        req = cc.request('apps')
        self.assertEqual('{0}/v3/apps'.format(cc_api_url), req.base_url)
