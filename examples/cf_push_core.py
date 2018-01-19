"""Deploys a Cloud Foundry application using a manifest
"""
from __future__ import print_function
import os
import sys
import json
import cf_api
from cf_api.deploy_manifest import Deploy
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

organization_name = raw_input('organization name: ').strip()
# see http://apidocs.cloudfoundry.org/280/organizations/list_all_organizations.html
# for an explanation of the query parameters
print('Searching for organization "{0}"...'.format(organization_name))
req = cc.request('organizations').set_query(q='name:' + organization_name)
res = req.get()
print(str(res.response.status_code) + ' ' + res.response.reason)
print('----------')
if res.has_error:
    print(str(res.error_code) + ': ' + str(res.error_message))
    sys.exit(1)

space_name = raw_input('space name: ').strip()
# see http://apidocs.cloudfoundry.org/280/spaces/list_all_spaces.html
# for an explanation of the query parameters
print('Searching for space...')
spaces_url = res.resource.spaces_url
req = cc.request(spaces_url).set_query(q='name:' + space_name)
res = req.get()
print(str(res.response.status_code) + ' ' + res.response.reason)
print('----------')
if res.has_error:
    print(str(res.error_code) + ': ' + str(res.error_message))
    sys.exit(1)

manifest_path = raw_input('manifest path: ').strip()
manifest_path = os.path.abspath(manifest_path)

app_entries = Deploy.parse_manifest(manifest_path, cc)
for app_entry in app_entries:
    app_entry.set_org_and_space(organization_name, space_name)
    app_entry.set_debug(True)
    app_entry.push()
    app_entry.wait_for_app_start(tailing=True)

print('Deployed {0} apps successfully!'.format(len(app_entries)))
