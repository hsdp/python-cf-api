.. _examples:

Examples
========

The following examples demonstrate the use cases of this library.

Initializing the Cloud Controller client
----------------------------------------

Create a new cloud controller client

.. code-block:: python

    import cf_api

    cc = cf_api.new_cloud_controller(
        'https://api.yourcloudfoundry.com',
        client_id='cf',
        client_secret='',
        username='myuser',
        password='uaapassword',
    )

    print(cc)

This code authenticates the user with UAA using the given client and user
credentials and, if authentication is successful, returns a Cloud Controller
request builder.

Making API requests with the Cloud Controller client
----------------------------------------------------

To make a request to the Cloud Controller API

.. code-block:: python

    import cf_api

    cc = cf_api.new_cloud_controller(...)

    request = cc.request('apps')
    response = request.get()

    print(response.data)

This code uses a cloud controller client object to create a new request for
the Cloud Controller API endpoint ``/v2/apps``, execute that request as an
HTTP GET request and print out a dictionary representation of the response.

.. note::

    Observe that the ``cc.request()`` method returns a
    :class:`~cf_api.CloudControllerRequest` object and does **NOT** execute the
    request. This allows the user to choose which HTTP method they want to execute.

The Request Object
------------------

Since the ``cc`` variable is an instance of the
:class:`~cf_api.CloudController` class, it is a "RequestFactory" instance,
which provides a method, :meth:`~cf_api.CloudController.request`, that produces
a "Request" object that is preset with the HTTP headers and base url from
the "RequestFactory" that produced it. This "Request" object has
several methods named for the HTTP verbs such as
:meth:`~cf_api.CloudControllerRequest.get` for GET,
:meth:`~cf_api.CloudControllerRequest.post` for POST,
:meth:`~cf_api.CloudControllerRequest.delete` for DELETE. You can set any query
parameters, body parameters, or headers on this "Request" object and the
parent "RequestFactory" will not be modified.

The :class:`~cf_api.CloudController` class provides many methods that are
convenience methods named after their respective Cloud Controller API
endpoints, such as :meth:`~cf_api.CloudController.organizations`,
:meth:`~cf_api.CloudController.spaces`, and
:meth:`~cf_api.CloudController.apps` which simply invoke
:meth:`~cf_api.CloudController.request` with single arguments of
``organizations``, ``spaces``, and ``apps``. This
:meth:`~cf_api.CloudController.request` method accepts a list of strings which
are joined to make a URL which is joined to the base URL of the
"RequestFactory", like so:

.. code-block:: python

    req = cc.request('organizations', org_guid, 'spaces')

The above example produces a "Request" object with a URL set to
``cloud_controller_url/v2/organizations/<org_guid>/spaces``.

An equivalent way to represent the above URL is as follows

.. code-block:: python

    req = cc.organizations(org_guid, 'spaces')

Executing the request object produces a
:class:`~cf_api.CloudControllerResponse` object. To execute the request as an
HTTP GET request, do

.. code-block:: python

    res = req.get()

Searching with the API endpoints
++++++++++++++++++++++++++++++++

The ``v2`` Cloud Controller API supports the same query syntax for every
endpoint it provides. This query syntax is 
``q=<search-key>:<some-resource-name>``.
The :class:`~cf_api.CloudControllerRequest` class provides a function,
:meth:`~cf_api.CloudControllerRequest.search`, that accepts a list of string
arguments in the form

.. code-block:: python

    org_name = 'myorg'
    space_guid = 'xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx'
    res = req.search('name', org_name, 'space_guid', space_guid)

This syntax sets the internal query parameters as follows
``q=name:<org_name>&q=space_guid:<space_guid>``.

Further query parameters may also be set using the keyword arguments, like so

.. code-block:: python

    org_name = 'myorg'
    res = req.search('name', org_name, **{'results-per-page': 10})

As searches by ``q=name:<some-name>`` are quite common, a further convenience
function is provided in the :meth:`~cf_api.CloudControllerRequest.get_by_name`
method, which is used like so

.. code-block:: python

    org_name = 'myorg'
    res = req.get_by_name(org_name)

Debugging a request
+++++++++++++++++++

The request object also exposes a method,
:meth:`~cf_api.CloudControllerRequest.get_requests_args`, which, when invoked,
returns the exact parameters that will be passed to the ``python-requests``
module to execute the Cloud Controller API request. The result is a tuple
containing:

1. the ``python-requests`` function that will be used (chosen based on the
   HTTP method set in the request object, i.e. ``requests.get``, etc)
2. the relative URL that will be invoked
3. the keyword arguments that will be passed into the ``python-requests``
   function.

.. note::

    The HTTP method **MUST** be set in order for this function to work
    correctly. You may get an exception if the method is not set! Often
    times the method is not set until the request is invoked with one of
    the functions that maps to the HTTP verbs (i.e. ``.get()`` or ``.post()``)
    and so, in order to view the request exactly as it would be executed,
    you must set the request method prior to invoking this function, using
    the :meth:`~cf_api.CloudControllerRequest.set_method` function.

.. code-block:: python

    print(req.set_query(...)\
             .set_header(...)\
             .set_params(...)\
             .set_method('POST')\
             .get_requests_args())

The Response Object
-------------------

The response object from an executed API request object is an instance of
:class:`~cf_api.CloudControllerResponse` class. This class has a few members
worth noting.

To access the response data as a simple :meth:`~dict`, use the
:attr:`~cf_api.CloudControllerResponse.data` attribute, like so

.. code-block:: python

    res = req.get()
    print(res.data)

This :attr:`~cf_api.CloudControllerResponse.data` attribute internally checks
if the request was successful (HTTP 200 range) and returns a simple
:class:`~dict` if successful, or throws an :class:`~exceptions.Exception`
if there was an error.

You can check if an error occurred using
:attr:`~cf_api.CloudControllerResponse.has_error`. You can get the error
code and message using :attr:`~cf_api.CloudControllerResponse.error_code` and
:attr:`~cf_api.CloudControllerResponse.error_message`.

The ``v2`` Cloud Controller API returns all its data types in the same
:class:`~cf_api.Resource` format, whether a list of results or a single result
object.

If you're searching for a single org by name using, for example, the
``organizations`` endpoint, you can reference the first result (assuming there
is only one result) like so

.. code-block:: python

    org_name = 'myorg'
    req = cc.organizations().search('name', org_name)
    res = req.get()
    my_org = res.resource

This works when requesting an organization by ID as well, like so

.. code-block:: python

    org_guid = 'xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx'
    req = cc.organizations(org_guid)
    res = req.get()
    my_org = res.resource

If your request returns a list of resources, then you can iterate over them
using the :attr:`~cf_api.CloudControllerResponse.resources` attribute, like so

.. code-block:: python

    res = cc.organizations().get()
    for org in res.resources:
        print(org)

If you want to access the raw response, use the
:attr:`~cf_api.CloudControllerResponse.raw_data` attribute to get a simple dict.
Accessing this attribute does not throw an error.

If you want to access the underlying ``python-requests`` Response object, you
can use the :attr:`~cf_api.CloudControllerResponse.response` attribute.

Getting all pages of a given resource list
------------------------------------------

To retrieve a paginated list of items, for example, a list of organizations.

.. code-block:: python

    import cf_api

    cc = cf_api.new_cloud_controller(...)
    req = cc.organizations()
    orgs = cc.get_all_resources(req)

.. note::

    Note that you **MUST NOT** execute HTTP GET method on the request.
    You must pass the prepared request object into the
    :meth:`~cf_api.CloudController.get_all_resources` method. This
    ``get_all_resources()`` method will internally execute an HTTP GET
    and store the results while ``next_url`` attribute is set on the
    response. Once there is no ``next_url`` the ``get_all_resources()`` method
    will return the aggregated list of resources.

Further examples
================

The following examples implement some common use cases for this library.

You can find the code for these examples in the ``examples`` directory.

Logging in
----------

The following examples demonstrate usage of the four grant types for
authentication with UAA.

Grant type: password
++++++++++++++++++++

.. literalinclude:: ../examples/cf_login.py
   :language: python

Grant type: authorization code
++++++++++++++++++++++++++++++

.. literalinclude:: ../examples/authenticate_with_authorization_code.py
   :language: python

Grant type: client credentials
++++++++++++++++++++++++++++++

.. literalinclude:: ../examples/authenticate_with_client_credentials.py
   :language: python

Grant type: refresh token
+++++++++++++++++++++++++

.. literalinclude:: ../examples/authenticate_with_refresh_token.py
   :language: python

Listing Organizations
---------------------

Think ``cf orgs``.

.. literalinclude:: ../examples/cf_orgs.py
   :language: python

Listing Spaces
--------------

Think ``cf spaces``.

.. literalinclude:: ../examples/cf_spaces.py
   :language: python

Listing Applications
--------------------

Think ``cf apps``.

This example shows how to list applications in a space using the standard
functions in :mod:`~cf_api`

.. literalinclude:: ../examples/cf_apps_core.py
   :language: python

This example shows how to list applications in a space using the
:mod:`~cf_api.deploy_space.Space` helper class.

.. literalinclude:: ../examples/cf_apps_simple.py
   :language: python

Deploying Applications in a space with a manifest (``cf push``)
---------------------------------------------------------------

This example shows how to deploy an application using the standard functions
in :mod:`~cf_api`

.. literalinclude:: ../examples/cf_push_core.py
   :language: python

This example shows how to deploy an applcation using the
:class:`~cf_api.deploy_space.Space` helper class.

.. literalinclude:: ../examples/cf_push_simple.py
   :language: python

Deploying Applications in a space with a manifest with no downtime
------------------------------------------------------------------

This example uses the :class:`~cf_api.deploy_blue_green.BlueGreen`
helper class.

.. literalinclude:: ../examples/cf_push_blue_green.py
    :language: python

Creating a service in a space
-----------------------------

.. literalinclude:: ../examples/cf_create_service.py
   :language: python

Tailing application logs
------------------------

This example shows how to tail an application's logs using the standard
functions in :mod:`~cf_api`

.. literalinclude:: ../examples/cf_logs_core.py
   :language: python

This example shows how to deploy an applcation using the
:mod:`~cf_api.deploy_space.Space` helper class.

.. literalinclude:: ../examples/cf_logs_simple.py
   :language: python

Looking up an application by its FQDN
--------------------------------------

If you have a CF app's domain name and you're not sure where it lives you can
find it using this example.

.. literalinclude:: ../examples/find_app_by_route.py
   :language: python
