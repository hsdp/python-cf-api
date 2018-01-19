"""Look up an application resource by it's route.
(i.e. host.domain(:port)?(/path)? )
"""
from __future__ import print_function
import sys
import cf_api
import json
from cf_api import routes_util
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
route_url = raw_input('route url: ').strip() # myapp.changme.com:4443/v2

print('----------')
apps = routes_util.get_route_apps_from_url(cc, route_url)

print('----------')
json.dump(apps, sys.stdout, indent=2)
print()
