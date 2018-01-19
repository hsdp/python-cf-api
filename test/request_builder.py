from __future__ import print_function
from settings import cf_api
import os
import requests
import unittest


BASE_URL = 'http://localhost'


class TestRequestFactory(unittest.TestCase):
    mixin = None

    def setUp(self):
        self.factory = cf_api.RequestFactory().set_base_url('http://localhost')

    def tearDown(self):
        self.factory = None

    def test_form_urlencoded(self):
        self.factory.form_urlencoded()
        self.assertEqual(self.factory.headers['Content-Type'],
                         'application/x-www-form-urlencoded')

    def test_application_json(self):
        self.factory.application_json()
        self.assertEqual(self.factory.headers['Content-Type'],
                         'application/json')

    def test_accept_json(self):
        self.factory.accept_json()
        self.assertEqual(self.factory.headers['Accept'],
                         'application/json')

    def test_set_verify_ssl(self):
        self.factory.set_verify_ssl(True)
        self.assertTrue(self.factory.verify_ssl)

        self.factory.set_verify_ssl(False)
        self.assertFalse(self.factory.verify_ssl)

    def test_set_basic_auth(self):
        self.factory.set_basic_auth('abc', 'def')
        self.assertEqual(self.factory.headers['Authorization'],
                         'Basic YWJjOmRlZg==')

    def test_set_bearer_auth(self):
        self.factory.set_bearer_auth('abc123')
        self.assertEqual(self.factory.headers['Authorization'],
                         'bearer abc123')

    def test_set_auth(self):
        self.factory.set_auth('abc123')
        self.assertEqual(self.factory.headers['Authorization'],
                         'abc123')

    def test_set_header(self):
        self.factory.set_header('x-test', 'test')
        self.assertEqual(self.factory.headers['x-test'], 'test')

    def test_set_base_url(self):
        self.factory.set_base_url(BASE_URL)
        self.assertEqual(self.factory.base_url, BASE_URL)

    def test_set_response_class(self):
        self.factory.set_response_class(cf_api.Response)
        self.assertEqual(self.factory.response_class, cf_api.Response)

    def test_set_callback(self):
        def cb(*args, **kwargs):
            pass
        self.factory.set_callback(cb)
        self.assertEqual(self.factory.callback, (cb, (), {}))

    def test_get_url(self):
        abcurl = BASE_URL + '/abc'
        defurl = BASE_URL + '/def'
        self.assertEqual(self.factory.get_url('abc'), abcurl)
        self.assertEqual(self.factory.get_url('def'), defurl)
        self.assertEqual(self.factory.base_url, BASE_URL)

    def test_add_url(self):
        self.factory.add_url('abc')
        self.assertEqual(self.factory.base_url, BASE_URL + '/abc')
        self.factory.add_url('def')
        self.assertEqual(self.factory.base_url, BASE_URL + '/abc/def')

    def test_request(self):
        req = self.factory.request('abc')
        self.assertTrue(isinstance(req, cf_api.Request))

    def test_set_request_class(self):
        class TestReq(cf_api.Request):
            pass
        self.factory.set_request_class(TestReq)
        req = self.factory.request('abc')
        self.assertTrue(isinstance(req, TestReq))


class TestRequest(unittest.TestCase):
    def setUp(self):
        self.factory = cf_api.RequestFactory().set_base_url(BASE_URL)
        self.req = self.factory.request('abc')

    def tearDown(self):
        self.factory = None
        self.req = None

    def test_set_method(self):
        self.req.set_method('GET')
        self.assertEqual(self.req.method, 'GET')

    def test_set_params(self):
        params = {'test': '123'}
        self.req.set_params(params)
        self.assertEqual(self.req.params, params)
        params = {'test': '1234'}
        self.req.set_params(**params)
        self.assertEqual(self.req.params, params)

    def test_set_query(self):
        qargs = {'test1': 1, 'test2': 2}
        self.req.set_query(**qargs)
        qlist = [('test1', 1), ('test2', 2)]
        self.assertEqual(qlist, self.req.query)
        qlist.append(('test1', 3))
        self.req.set_query(*qlist)
        self.assertEqual(qlist, self.req.query)

    def test_set_body_param(self):
        body = {'a': 'b'}
        self.req.param('a', 'b')
        self.assertEqual(self.req.params, body)

    def test_add_field(self):
        mpfiles = {'a': (None, 'b')}
        self.req.add_field('a', 'b')
        self.assertEqual(self.req.multipart_files, mpfiles)

    def test_add_file(self):
        fn = os.path.abspath(__file__)
        with open(fn, 'r') as f:
            mpfiles = {'a': ('test.py', f, 'application/python')}
            self.req.add_file('a', 'test.py', f, 'application/python')
            self.assertEqual(mpfiles, self.req.multipart_files)

    def test_get_requests_args(self):
        requests_args = self.req.set_method('GET').get_requests_args()
        self.assertEqual(requests_args, (
            getattr(self.req.session, self.req.method.lower()),
            BASE_URL + '/abc',
            {'data': {}, 'headers': {}, 'verify': True}
        ))
