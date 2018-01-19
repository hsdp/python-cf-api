"""Log in with UAA client credentials (using grant_type "client_credentials")
"""
from __future__ import print_function
import sys
import json
import cf_api
from getpass import getpass


print('----------')
# cloud_controller_url = 'https://api.changeme.com'
cloud_controller_url = raw_input('cloud controller url: ').strip()
client_id = raw_input('client id: ').strip()
client_secret = getpass('client secret: ').strip()

print('----------')
print('Authenticating with UAA...')
cc = cf_api.new_cloud_controller(
    cloud_controller_url,
    client_id=client_id,
    client_secret=client_secret,
)
print('Login OK!')

print('----------')
access_token = cc.uaa.get_access_token()
print('access_token: ' + str(access_token) + '\n')
print('access_token_data:')
json.dump(access_token.attrs, sys.stdout, indent=2)
print()
