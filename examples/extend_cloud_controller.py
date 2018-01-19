from __future__ import print_function
import cf_api
from getpass import getpass


class MyUAA(cf_api.UAA):
    pass


class MyCloudController(cf_api.CloudController):
    pass


print('----------')
# cloud_controller_url = 'https://api.changeme.com'
cloud_controller_url = raw_input('cloud controller url: ').strip()
username = raw_input('username: ').strip()
password = getpass('password: ').strip()

print('----------')
print('Authenticating with UAA...')
cc = MyCloudController.new_instance(
        base_url=cloud_controller_url,
        username=username,
        password=password,
        client_id='cf',
        client_secret='',
        uaa_class=MyUAA,
)
print('Login OK!')

print('----------')
print('cc isinstance of MyCloudController?', isinstance(cc, MyCloudController))
print('cc.uaa isinstance of MyUAA?', isinstance(cc.uaa, MyUAA))
print()
