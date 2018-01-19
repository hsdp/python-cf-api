"""Deploys a Cloud Foundry application using a manifest
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

app_entries = space.get_deploy_manifest(manifest_path)
for app_entry in app_entries:
    app_entry.push()
    app_entry.wait_for_app_start(tailing=True)

print('Deployed {0} apps successfully!'.format(len(app_entries)))
