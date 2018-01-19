import re
import json
import requests
import requests_mock
from uuid import uuid4
from settings import cf_api
from settings import BASE_URL

USERNAME = 'test'
PASSWORD = 'tset'

UAA_ACCESS_TOKEN = 'abc'
UAA_REFRESH_TOKEN = 'def'

TYPE_JSON = 'application/json'

CC_RES_INFO = json.dumps({
    'token_endpoint': BASE_URL,
    'doppler_logging_endpoint': BASE_URL
    })

UAA_RES_OAUTH_TOKEN = json.dumps({
    'access_token': UAA_ACCESS_TOKEN,
    'refresh_token': UAA_REFRESH_TOKEN
    })

UAA_REQUIRED_HEADERS = {
    #'Content-Type': TYPE_JSON,
    #'Accept': TYPE_JSON
}

def get_cc_url(rel):
    return '/'.join([BASE_URL, 'v2', rel])


def get_uaa_url(rel):
    return '/'.join([BASE_URL, rel])


def cc_expect_info(m):
    m.get(get_cc_url('info'), text=CC_RES_INFO)


def uaa_expect_oauth_token(m):
    m.post(get_uaa_url('oauth/token'), text=UAA_RES_OAUTH_TOKEN)


def expect_new_cloud_controller(m):
    cc_expect_info(m)
    uaa_expect_oauth_token(m)

def expect_new_uaa(m):
    expect_new_cloud_controller(m)
