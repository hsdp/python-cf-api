"""Searches for apps in a space in an organization on the Cloud Controller API
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
print('Searching for space "{0}"...'.format(space_name))
spaces_url = res.resource.spaces_url
req = cc.request(spaces_url).set_query(q='name:' + space_name)
res = req.get()

print(str(res.response.status_code) + ' ' + res.response.reason)
print('----------')

if res.has_error:
    print(str(res.error_code) + ': ' + str(res.error_message))
    sys.exit(1)

print('Searching for apps in "{0} / {1}"...'.format(
      organization_name, space_name))
first_space = res.resource
space_apps_url = first_space.apps_url
req = cc.request(space_apps_url)
res = cc.get_all_resources(req)

print('----------')
json.dump(res, sys.stdout, indent=2)
print()
