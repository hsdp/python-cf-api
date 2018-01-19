"""Log in with UAA refresh token (using grant_type "refresh_token")

The if the user has CF CLI installed this script checks for
``~/.cf/config.json`` and reads the refresh token from there, otherwise,
the user is asked to enter client credentials and the refresh token
"""
from __future__ import print_function
import os
import sys
import json
import cf_api
from getpass import getpass


cloud_controller_url = raw_input('cloud controller url: ').strip()
config_file = os.path.expanduser('~/.cf/config.json')
print('----------')
if os.path.isfile(config_file):
    print('Loading refresh token from ~/.cf/config.json ...')
    with open(config_file) as f:
        config = json.load(f)
        refresh_token = config['RefreshToken']
        client_id = 'cf'
        client_secret = ''
else:
    client_id = raw_input('client id: ').strip()
    client_secret = getpass('client secret: ').strip()
    refresh_token = raw_input('refresh token: ').strip()

print('----------')
print('Authenticating with UAA...')
cc = cf_api.new_cloud_controller(
    cloud_controller_url,
    client_id=client_id,
    client_secret=client_secret,
    refresh_token=refresh_token,
)

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
