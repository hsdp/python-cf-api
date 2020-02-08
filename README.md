# Python Interface for Cloud Foundry APIs

This is the next-generation edition of `cf_api` Cloud Foundry API client.

## Features

- Minimal dependencies: only requires `requests`
- Simplicity: the whole library is a single file
- Supports both v2 and v3 Cloud Foundry APIs
- Automatic access token refreshing
- Fluent interface for building requests
- Transparently supports v2 and v3 pagination
- Supports making requests scoped to a single CF space
- Unit tested
- Still supports Python 2.7

## Rationale

Some API clients provide a function for every possible API call. It's a decent
way to implement a client, but it often requires code generation, and always
produces thousands of lines of code, which must be maintained. This
implementation does not provide a function for every API call, but rather aims
to make building and sending CF API requests easy, as well as maintainable and
simple.

## Install

To install,

```
pip install cf-api==2.0.0a2
```

## Testing

To run the tests,

```
make test
```

## How to use

The following sections provide guidance on how to use this library.

### Configuration

By default, the library reads it's configuration from environment variables.

| Name | Description
| --- | ---
| *CF_URL* | Cloud Foundry API endpoint
| *CF_VERSION* | Cloud Foundry API version (only supports `v2` or `v3` at this time)
| *CF_USERNAME* | UAA username
| *CF_PASSWORD* | UAA password
| *CF_CLIENT_ID* | UAA client ID (defaults to `cf`)
| *CF_CLIENT_SECRET* | UAA client secret (defaults to empty string)

```python
import cf_api
config = cf_api.Config()
```

The `Config` object is used to configure the CF API client `CloudController`.

### CloudController and new_cloud_controller()

The `CloudController` object is the CF API client. The `new_cloud_controller()`
function should be used to construct new instances of `CloudController`.

```python
import cf_api
config = cf_api.Config()
cc = cf_api.new_cloud_controller(config)  # produces an instance of CloudController
```

#### Make a v2 request

```python
req = cc.v2('apps')
print(req.url)  # produces the url http://cfdomain/v2/apps
```

#### Make a v3 request

```python
req = cc.v3('apps')
print(req.url)  # produces the url http://cfdomain/v3/apps
```

#### Make a request using config.version

The `CloudController` builds `Request` objects configured with the proper API version.

```python
config.version = 'v3'
req = cc.request('apps')
print(req.url)  # produces the url http://cfdomain/v3/apps
```

### Request objects

```python
cc.config.version = 'v3'
req = cc.request('apps')  # this produces an instance of cf_api.V3Request
print(req.url)  # this produces a url of 'https://cfdomain/v3/apps'
res = req.get()  # this sends the request as GET, and returns an instance of V3Response
print(res.data)  # this is a dictionary of the literal JSON response
print(res.ok)  # indicates whether the request got a 2xx response or not
```

#### Set a JSON POST/PUT body

```python
app_guid = '<RANDOM_APP_GUID>'
app_instances = {'instances': 1}
res = cc.request('apps', app_guid).set_body(app_instances).put()
print(res.data)  # should produce a dictionary of your updated app
```

Note that you can pass URL path segments as individual args and they will be
concatenated into the full URL path (i.e. `/<version>/apps/<RANDOM_APP_GUID`).

#### Send an obscure HTTP method

Should you ever need to send a more obscure HTTP method, you may use the `req.send()`
method.

```python
req = cc.request('apps', app_guid).send('LIST')
print(res.data)
```

#### Easily follow URLs from API resources

Cloud Foundry resources objects often provide prebuilt URLs to related objects.
For example, a CF application often links to it's parent CF space.

```
{
    "metadata": {
        "guid": "..."
    },
    "entity": {
        "name": "my-app",
        "space_url": "/v2/spaces/space-guid"
    }
}
```

#### Fluent interface

`Request` objects support a fluent interface. Invoking a `Request` object as a
function, will append the argument(s) to the URL as a path segments.

```python
app_guid = '<APPGUID>'
req = cc.v2
print(req.apps(app_guid).url)  # produces http://cfdomain/v2/apps/<APPGUID>
```

Unimplemented `Request` class attributes will also be appended as path attributes.
The following example shows the usage of `apps` as an unimplemented attribute.

```python
app_guid = '<APPGUID>'
req = cc.v2
print(req.apps.url)  # produces http://cfdomain/v2/apps
```

Here is another example to get all apps in a space.

```python
space_guid = '<SPACEGUID>'
print(cc.v2.spaces(space_guid).apps.url)  # produces http://cfdomain/v2/spaces/<SPACEGUID>/apps
```

### Response objects

The `Request.send()` method always produces an instance of `Response` which
wraps the JSON dictionary response from the CF API and provides a couple
convenience methods for interacting with the top-level API response attributes.

#### Check if the response was 2xx or not

```python
res = cc.request('apps', app_guid).get()
print(res.ok)  # produces a boolean indicating 2xx or not
```

#### Check if there's another page

```python
res = cc.request('apps').get()
print(res.next_url)  # produces the next_url if there's another page otherwise None
```

Note that the `next_url` attribute is used in the `iterate_all_resources()` to
get all pages of a resource.

#### Get a wrapped resource object(s)

Getting a single API resource

```python
res = cc.request('apps', app_guid).get()
print(res.resource)  # will be an instance of V2Resource
```

Getting a list of API resources

```python
res = cc.request('apps').get()
print([r.name for r in res.resources])  # will be a list of V2Resource objects
```

### Resource objects

`Resource` objects provide API version agnostic attributes to get commonly used
API resource attributes such as GUID, name, label, host, space_guid, and org_guid.
For example, in API v2 `guid` is referenced in `.metadata.guid` but in `v3` it is referenced
in `.guid`. As another example, in API v2 `space_guid` is referenced in `.entity.space_guid`
but in `v3` it is referenced in `.relationships.space.data.guid`. The `Resource` object
makes it easy to work with both versions.

All the attributes have not been included in the interest of brevity, however,
it is possible to extend these classes and add your own customizations.

To access common attributes

```python
res = cc.request('apps', app_guid).get()
rsc = res.resource  # should be an instance of V2Resource
print(rsc.guid, rsc.name, rsc.space_guid)
```

You may configure a `Response` object's `resource_class` attribute, with a
customized `Resource` class of your own.

```python
class MyResource(V3Resource):
    pass

class MyResponse(V3Response):
    resource_class = MyResource

class MyRequest(V3Request):
    response_class = MyResponse

myconfig = cf_api.Config()
myconfig.request_class = MyRequest

mycc = cf_api.new_cloud_controller(myconfig)
req = mycc.request('apps')  # produces instance of MyRequest
res = req.get()  # produces instance of MyResponse
print(res.resource)  # produces instance of MyResource
```

Note that `cc.v2()` and `cc.v3()` will NOT use your customized request class.

#### Accessing name, guid, \*\_url, and \*\_guid

Both `V2Resource` and `V3Resource`, support accessing any resource attribute that
ends with `*_url` or `*_guid`. This means that the following example works
regardless of version.

```python
v2res = cc.v2.apps.get().resource
v3res = cc.v3.apps.get().resource
assert v2res.space_url == v3res.space_url
assert v2res.space_guid == v3res.space_guid
assert v2res.guid == v3res.guid
assert v2res.name == v3res.name
# these comparisons should all be ok
```

### Space objects

The `Space` object looks up a space by it's GUID or by it's org and space name
and builds requests that are scoped to the space in an API version agnostic manner.

#### Initialize a space object

```python
org_name = 'my_org'
space_name = 'my_space'
cc.config.version = 'v2'
space = Space(cc).init_by_name(org_name, space_name)
space_guid = space.space.guid  # space.space is a V2Resource
org_guid = space.org.guid  # space.org is a V2Resource
print(space_guid)  # shows the space's guid
```

#### Make a space scoped API request

For example, list all apps in a space using API v2

```python
space.cc.config.version = 'v2'
req = space.request('apps')
assert req.url == 'https://cfdomain/v2/apps?q=space_guid:' + space_guid
# should be ok
```

OR using API v3

```python
space.cc.config.version = 'v3'
req = space.request('apps')
assert req.url == 'https://cfdomain/v3/apps?space_guids=' + space_guid
# should be ok
```

The above example also works for any API resource that supports the `space_guid`
filter (i.e. `service_instances`). Note that filtering `routes` resources by space
is not supported in API v2, but is supported in API v3.

#### Space shortcuts

The following methods create a space object without an intermediate `CloudController` object.

Use the org and space name to create a `Space` instance.

```python
space = get_space_by_name(org_name, space_name)  # produces initialized Space object
```

Use the space guid to create a `Space` instance.

```python
space = get_space_by_guid(space_guid)  # produces initialized Space object
```

### Get all pages of a resource

The `iterate_all_resources()` function handles pagination. It accepts a
`Request` object and makes GET requests following the `next_url` attribute until
no more pages are returned. V2 and v3 are supported transparently. This is a
generator function, therefore on each page it yields the individual resources.

For example, let's use `iterate_all_resources()` to list all apps in a space.

```python
req = space.request('apps')
for app in iterate_all_resources(req):
    print(app)
```

If you want to assemble the entire list of resources before iterating it, you
may use a list comprehension.

```python
req = space.request('apps')
apps = [app for app in iterate_all_resources(req)]
for app in apps:
    print(app)
```

## License

Apache License Version 2.0
