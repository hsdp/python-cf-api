# Python Cloud Foundry API Client

This module provides a pure Python interface to the Cloud Foundry APIs.

## Installation

You can install from PIP

`pip install cf-api`

or view it on [PyPI](https://pypi.python.org/pypi/cf_api).

## Documentation

See the docs at [https://cf-api.readthedocs.io/en/latest/](https://cf-api.readthedocs.io/en/latest/) or in the [./docs](docs) directory and the [./examples](examples) directory.

## Versioning

*Version 1.x*
- Support both Python 2.7/3.6-3.8
- Remove `cf_api.dropsonde` module in favor of the `dropsonde` module.
- Add CF API version 3 support
- Add `Dockerfile` example

*Version 0.x*
- Supports Python 2.7

## Getting Started

The following examples should be enough to get you started using this library.

```python
# Initializing the Cloud Controller client

from getpass import getpass
import cf_api
import json

cloud_controller = 'https://api.yourcloudfoundry.com'
deploy_client_id = 'cf'
deploy_client_secret = ''
verify_ssl = True
username = 'youser'
password = getpass('Password: ').strip()

cc = cf_api.new_cloud_controller(
    cloud_controller,
    client_id=deploy_client_id,
    client_secret=deploy_client_secret,
    username=username,
    password=password,
).set_verify_ssl(verify_ssl)
    
    
# List all organizations
req = cc.organizations()
res = req.get()
orgs = res.resources
for r in orgs:
    print('org', r.guid, r.name)
    
    
# List all spaces
res = cc.spaces().get()
spaces = res.resources
for r in spaces:
    print('space', r.guid, r.name)


# List all applications

res = cc.apps().get()
apps = res.resources
for r in apps:
    print('app', r.guid, r.name)


# Find an app by it's org/space/name

org_name = 'your_org'
space_name = 'your_space'
app_name = 'your_app'

# find your org by name
res = cc.organizations().get_by_name(org_name)
# you can access the first array resource using the `resource` attribute
your_org = res.resource

# find your space by name within your org
res = cc.request(your_org.spaces_url).get_by_name(space_name)
your_space = res.resource

# find your app by name within your space
res = cc.request(your_space.apps_url).get_by_name(app_name)
your_app = res.resource
print('your_app', your_app)


# Find an app by it's GUID
# 
# Note that this same pattern applies to all Cloud Controller resources
#

res = cc.apps(your_app.guid).get()
# you can also use the `resource` attribute to access a response with a 
# non-array result
your_same_app = res.resource
print('your_same_app', your_same_app)


# Find a stack by name
your_stack = 'some_stack'
res = cc.stacks().get_by_name(your_stack)
stack = res.resource


# Create an app
your_buildpack = 'some_buildpack'
command = 'python server.py'
res = cc.apps().set_params(
    name=app_name,
    space_guid=your_space.guid,
    stack_guid=stack.guid,
    buildpack=your_buildpack,
    command=command,
    health_check_type='port',
    health_check_timeout=60,
    instances=2,
    memory=512,
    disk_quota=512
).post()
print('new app', res.data)


# Upload the bits for an app
my_zipfile = '/tmp/app.zip'
with open(my_zipfile, 'r') as f:
    res = cc.apps(your_app.guid, 'bits')\
        .set_query(async='true')\
        .add_field('resources', json.dumps([]))\
        .add_file('application', 'application.zip', f, 'application/zip')\
        .put()
    print(res.data)
```

## Running in Docker

To get start running `cf_api` in Docker, just build the provided [Dockerfile](./Dockerfile)

```
you@yourhost:~/python-cf-api$ docker build -t python-cf-api:latest .
```

and run it using the following syntax.

```
you@yourhost:~/python-cf-api$ docker run --rm -it -v $PWD:/src -w /src python-cf-api:latest python3
Python 3.8.1
[GCC 9.2.0] on linux
Type "help", "copyright", "credits" or "license" for more information.
>>> import cf_api
>>> # play with it here
```

## Using CF API version 3

The following example shows how to use the Cloud Foundry version 3 API.

```python
import cf_api

cc = cf_api.new_cloud_controller()
req = cc.v3.apps()
res = req.get()
print(res.resource.guid)
```

- The `cc.v3` attribute returns a `CloudController` instance that is configured
  to wrap requests and responses in V3 compatible classes, namely `V3CloudControllerRequest`
  and `V3CloudControllerResponse`. These objects work similarly to their v2 counterparts,
  `CloudControllerRequest` and `CloudControllerResponse`.
- The `V3CloudControllerResponse` provides `resource` and `resources` which return
  an instance or list of instances of `V3Resource` objects which support the
  common API object keys such as `name`, `guid`, `space_guid`, and `org_guid`, etc.
- The `cc.v3.get_all_resources()` function supports both v2 and v3 pagination.
- The `cc.v3.request()` function supports _both_ relative URLs and absolute URLs,
  for example `/v3/apps` and `http://localhost/v3/apps`, respectively. See `request()`
  function documentation for more information.

## Environment Variables

The library is also configurable via environment variables.

| Variable | Description |
| --- | --- |
| `PYTHON_CF_URL` | This is the cloud controller base URL. **Do not include a trailing slash on the URL.**
| `PYTHON_CF_CLIENT_ID` | This is the UAA client ID the library should use.
| `PYTHON_CF_CLIENT_SECRET` | This is the UAA client secret the library should use.
| `PYTHON_CF_IGNORE_SSL` | This indicates whether to verify SSL certs. Default is false. Set to `true` to ignore SSL verification.
| `CF_DOCKER_PASSWORD` | This variable optionally provides the Docker user's password if a docker image is being used. This variable is not necessarily required to use a docker image.

An example library usage with these variables set would look like this:

```python
# env vars might be set as follows
# PYTHON_CF_URL=https://api.cloudfoundry.com
# PYTHON_CF_CLIENT_ID=my_client_id
# PYTHON_CF_CLIENT_SECRET=my_client_secret

import cf_api

# no args are required when the above env vars are detected
cc = cf_api.new_cloud_controller()
res = cc.apps().get()
# ...

# the same principle applies to new_uaa()
uaa = cf_api.new_uaa()
# ...
```

## Log in with Cloud Foundry Authorization Code

The following functions may be used to implement login with Cloud Foundry via Authorization Codes.

The function `get_openid_connect_url()` shows how to build UAA URL to which the user can be 
redirected in order to log in.
  
The function `verify_code()` can be used when the user successfully logs in and UAA redirects back
to redirect_uri with the `code` attached. Pass the code and original redirect_uri into this function
in order to get the OAuth2 Token and to also verify the signature of the JWT.

This particular example applies to OpenID Connect.

```python
import cf_api

cc = 'https://api.yourcloudfoundry.com'
client_id = 'yourclient'
client_secret = 'yoursecret'
response_type = 'code'

def get_openid_connect_url(redirect_uri):
    return cf_api\
        .new_uaa(cc=cc, client_id=client_id, client_secret=client_secret, no_auth=True)\
        .authorization_code_url(response_type, scope='openid', redirect_uri=redirect_uri)


def verify_code(code, redirect_uri):
    uaa = cf_api.new_uaa(cc=cc, client_id=client_id, client_secret=client_secret, no_auth=True)
    res = uaa.authorization_code(code, response_type, redirect_uri)
    data = res.data
    uaa.verify_token(data['id_token'], audience=uaa.client_id)
    return data
```

## Deploy an Application

The `cf_api.deploy_manifest` module may be used to deploy a Cloud Foundry app. The 
following snippet demonstrates the usage for deploying an app.

```bash
cd path/to/your/project
python -m cf_api.deploy_manifest \
  --cloud-controller https://api.yourcloudfoundry.com \
  -u youser -o yourg -s yourspace \
  -m manifest.yml -v -w
# For the CLI usage of deploy_manifest, you may also set
#   the CF_REFRESH_TOKEN environment variable as a substitute
#   for collecting username and password
```

This module may also be used programmatically.
 
```python
from __future__ import print_function
import cf_api
from getpass import getpass
from cf_api.deploy_manifest import Deploy

cc = cf_api.new_cloud_controller(
    'https://api.yourcloudfoundry.com',
    username='youruser',
    password=getpass().strip(),
    client_id='cf',
    client_secret='',
    verify_ssl=True
)

manifest_filename = 'path/to/manifest.yml'

apps = Deploy.parse_manifest(manifest_filename, cc)

for app in apps:
    app.set_debug(True)
    app.set_org_and_space('yourorg', 'yourspace')
    print (app.push()) 
    # print (app.destroy(destroy_routes=True))
```

## Deploy a Service

The `cf_api.deploy_service` module may be used to deploy a Cloud Foundry service to a space. The 
following snippet demonstrates the usage for deploying a service.

```bash
cd path/to/your/project
python -m cf_api.deploy_service \
  --cloud-controller https://api.yourcloudfoundry.com \
  -u youser -o yourg -s yourspace \
  --name your-custom-service-name --service-name cf-service-type \
  --service-plan cf-service-type-plan -v -w
```

This module may also be used programmatically.

```python
from __future__ import print_function
import cf_api
from getpass import getpass
from cf_api.deploy_service import DeployService

cc = cf_api.new_cloud_controller(
    'https://api.yourcloudfoundry.com',
    username='youruser',
    password=getpass().strip(),
    client_id='cf',
    client_secret='',
    verify_ssl=True
)

service = DeployService(cc)\
    .set_debug(True)\
    .set_org_and_space('yourorg', 'yourspace')
    
result = service.create('my-custom-db', 'database-service', 'small-database-plan')
print(result)
```

## Query a Space

The `cf_api.deploy_space` module provides a convenience interface for working with Cloud Foundry
spaces. The module provides read-only (i.e. GET requests only) support for the Cloud Controller API
endpoints scoped to a specific space i.e. /v2/spaces/<space_guid>/(routes|service_instances|apps).
The following snippet demonstrates the usage for listing apps for in a space.

```bash
cd path/to/your/project
python -m cf_api.deploy_space \
  --cloud-controller https://api.yourcloudfoundry.com \
  -u youser -o yourg -s yourspace apps
```

This module may also be used programmatically.

```python
from __future__ import print_function
import cf_api
from getpass import getpass
from cf_api.deploy_space import Space

cc = cf_api.new_cloud_controller(
    'https://api.yourcloudfoundry.com',
    username='youruser',
    password=getpass().strip(),
    client_id='cf',
    client_secret='',
    verify_ssl=True
)

space = Space(cc, org_name='yourorg', space_name='yourspace')

# create the space
space.create()

# destroy the space
space.destroy()

# make a Cloud Controller request within the space
apps_in_the_space = space.request('apps').get()

# deploys an application to this space
space.deploy_manifest('/path/to/manifest.yml') # push the app
space.wait_manifest('/path/to/manifest.yml') # wait for the app to start
space.destroy_manifest('/path/to/manifest.yml') # destroy the app

app = space.get_app_by_name('yourappname') # find an application by its name within the space

# deploy a service in this space
space.get_deploy_service().create('my-custom-db', 'database-service', 'small-database-plan')
service = space.get_service_instance_by_name('my-custom-db') # find a service by its name within the space
```

## Tail Application Logs

The `cf_api.logs_util` module may be used to tail Cloud Foundry application logs. Both
`recentlogs` and `stream` modes are supported. The following snippet demonstrates the usage for
listing recent logs and tailing app logs simultaneously.

```bash
cd path/to/your/project
python -m cf_api.logs_util \
  --cloud-controller https://api.yourcloudfoundry.com \
  -u youser -o yourg -s yourspace -a yourapp \
  -r -t
```

This module may also be used programmatically.

```python
from __future__ import print_function
import cf_api
from getpass import getpass
from cf_api import dropsonde_util

cc = cf_api.new_cloud_controller(
    'https://api.yourcloudfoundry.com',
    username='youruser',
    password=getpass().strip(),
    client_id='cf',
    client_secret='',
    verify_ssl=True,
    init_doppler=True
)

app_guid = 'your-app-guid'
app = cc.apps(app_guid).get().resource

# get recent logs
logs = cc.doppler.apps(app.guid, 'recentlogs').get().multipart

# convert log envelopes from protobuf to dict
logs = [dropsonde_util.parse_envelope_protobuf(log) for log in logs]

print(logs)

# stream logs
ws = cc.doppler.ws_request('apps', app.guid, 'stream')
try:
    ws.connect()
    ws.watch(lambda m: print(dropsonde_util.parse_envelope_protobuf(m)))
except Exception as e:
    print(e)
finally:
    ws.close()
```
