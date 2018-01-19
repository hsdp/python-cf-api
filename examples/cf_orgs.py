"""Searches for an organization by name on the Cloud Controller API
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

print('Searching for organizations...')
req = cc.request('organizations')
resources_list = cc.get_all_resources(req)

print('----------')
json.dump(resources_list, sys.stdout, indent=2)
print()
