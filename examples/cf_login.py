"""Log in with your UAA user credentials (using grant_type "password")

This example mimics the CF login action and uses the same "cf" client that
the CF CLI uses.
"""
from __future__ import print_function
import sys
import json
import cf_api
from getpass import getpass


print('----------')
# cloud_controller_url = 'https://api.changeme.com'
cloud_controller_url = raw_input('cloud controller url: ').strip()
username = raw_input('username: ').strip()
password = getpass('password: ').strip()

print('----------')
print('Authenticating with UAA...')
cc = cf_api.new_cloud_controller(
    cloud_controller_url,
    client_id='cf',  # the ``cf`` command uses this client and the secret below
    client_secret='',
    username=username,
    password=password,
)
print('Login OK!')

print('----------')
access_token = cc.uaa.get_access_token()
refresh_token = cc.uaa.get_refresh_token()
print('access_token: ' + access_token.to_string() + '\n')
print('refresh_token: ' + refresh_token.to_string() + '\n')
print('user_id: ' + access_token.user_id + '\n')
print('user_name: ' + access_token.user_name + '\n')
print('access_token_data:')
json.dump(access_token.attrs, sys.stdout, indent=2)
print()
