"""Searches for spaces in an organization by name on the Cloud Controller API
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
if res.has_error:
    print(str(res.error_code) + ': ' + str(res.error_message))
    sys.exit(1)

print('----------')
print('Searching for spaces in "{0}"...'.format(organization_name))
first_org = res.resource
org_spaces_url = first_org.spaces_url
req = cc.request(org_spaces_url)
resources_list = cc.get_all_resources(req)

print('----------')
json.dump(resources_list, sys.stdout, indent=2)
print()
