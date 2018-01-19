"""Runs a Blue Green deploy of a Cloud Foundry application using a manifest
"""
from __future__ import print_function
import os
import sys
import json
import cf_api
from cf_api.deploy_manifest import Deploy
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
space = Space(cc, org_name=org_name, space_name=space_name, is_debug=True)
print('Found space!')

print('----------')
manifest_path = raw_input('manifest path: ').strip()
manifest_path = os.path.abspath(manifest_path)

space.deploy_blue_green(manifest_path)
print('Deployed {0} successfully!'.format(app_name))
