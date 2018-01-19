"""Tails application logs like ``cf logs``
"""
from __future__ import print_function
import sys
import cf_api
from getpass import getpass
from cf_api.dropsonde_util import DopplerEnvelope
from cf_api.deploy_space import Space


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
print('Looking up org space "{0} / {1}"...'.format(org_name, space_name))
space = Space(cc, org_name=org_name, space_name=space_name, is_debug=True)
print('Found space!')

print('----------')
app_name = raw_input('app name: ').strip()
print('Looking up app "{0}" in "{1} / {2}"...'
      .format(app_name, org_name, space_name))
app = space.get_app_by_name(app_name)
print('Found app!')

print('----------')
print('Connecting to app log stream "{0}"...'.format(app_name))
websocket = cc.doppler.ws_request('apps', app.guid, 'stream')
websocket.connect()
print('Connected and tailing logs for "{0}" in "{1} / {2}"!'.format(
        org_name, space_name, app_name))

print('----------')

def render_log(msg):
    d = DopplerEnvelope.wrap(msg)
    sys.stdout.write(''.join([str(d), '\n']))
    sys.stdout.flush()

websocket.watch(render_log)
