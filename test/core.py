from __future__ import print_function
import os
import json
import requests_mock
import unittest
from settings import cf_api
from settings import IS_MOCKING
from settings import BASE_URL
import mocks
from mocks import UAA_ACCESS_TOKEN
from mocks import USERNAME
from mocks import PASSWORD


class TestNewCloudController(unittest.TestCase):
    def test_no_args(self):
        with requests_mock.mock() as m:
            mocks.expect_new_cloud_controller(m)
            cc = cf_api.new_cloud_controller()
            self.assertTrue(isinstance(cc, cf_api.CloudController))
            self.assertTrue(isinstance(cc.uaa, cf_api.UAA))
            self.assertEqual(cc.uaa.access_token, UAA_ACCESS_TOKEN)


class TestNewUAA(unittest.TestCase):
    def test_no_args(self):
        with requests_mock.mock() as m:
            mocks.expect_new_uaa(m)
            uaa = cf_api.new_uaa()
            self.assertTrue(isinstance(uaa, cf_api.UAA))
            self.assertEqual(uaa.access_token, UAA_ACCESS_TOKEN)
