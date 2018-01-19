"""Tails application logs like ``cf logs``

This example shows how to use the core :module:`~cf_api` module to tail
the logs of an application.
"""
from __future__ import print_function
import sys
from getpass import getpass
import cf_api
from cf_api.dropsonde_util import DopplerEnvelope


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
res = cc.organizations().get_by_name(org_name)
print(str(res.response.status_code) + ' ' + res.response.reason)
if res.has_error:
    print(str(res.error_code) + ': ' + str(res.error_message))
    sys.exit(1)

print('----------')
space_name = raw_input('space name: ').strip()
res = cc.request(res.resource.spaces_url).get_by_name(space_name)
print(str(res.response.status_code) + ' ' + res.response.reason)
if res.has_error:
    print(str(res.error_code) + ': ' + str(res.error_message))
    sys.exit(1)

print('----------')
app_name = raw_input('app name: ').strip()
res = cc.request(res.resource.apps_url).get_by_name(app_name)
print(str(res.response.status_code) + ' ' + res.response.reason)
if res.has_error:
    print(str(res.error_code) + ': ' + str(res.error_message))
    sys.exit(1)

print('----------')
websocket = cc.doppler.ws_request('apps', res.resource.guid, 'stream')
websocket.connect()
print('Connected and tailing logs for "{0}" in "{1} / {2}"!'.format(
    org_name, space_name, app_name))

print('----------')

def render_log(msg):
    d = DopplerEnvelope.wrap(msg)
    sys.stdout.write(''.join([str(d), '\n']))
    sys.stdout.flush()

websocket.watch(render_log)
