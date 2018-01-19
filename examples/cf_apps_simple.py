"""Searches for apps in a space in an organization on the Cloud Controller API
"""
from __future__ import print_function
import sys
import json
import cf_api
from cf_api.deploy_space import Space
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
org_name = raw_input('organization name: ').strip()
space_name = raw_input('space name: ').strip()
print('Looking up "{0} / {1}"...'.format(org_name, space_name))
space = Space(cc, org_name=org_name, space_name=space_name)
print('Found space!')

print('----------')
print('Searching for apps in "{0} / {1}"...'.format(org_name, space_name))
apps = space.request('apps').get().data
print('Found apps!')

print('----------')
json.dump(apps, sys.stdout, indent=2)
print()
