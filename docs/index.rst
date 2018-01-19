.. cf-api documentation master file, created by
   sphinx-quickstart on Wed Dec  6 10:27:19 2017.
   You can adapt this file completely to your liking, but it should at least
   contain the root `toctree` directive.

Welcome to cf-api's documentation!
==================================

.. toctree::
    :maxdepth: 2

    api
    examples

The cf-api library provides a pure Python interface to the Cloud Foundry APIs. Supported features include the following:

- `Authenticated Cloud Controller HTTP request builder <api.html#cf_api.new_cloud_controller>`_
- `UAA OAuth2 implementations for all grant types <api.html#cf_api.new_uaa>`_
- `Support for deploying Cloud Foundry applications from an application manifest <api.html#cf_api.deploy_manifest.Deploy>`_
- `Helper for deploying Cloud Foundry services <api.html#cf_api.deploy_service.DeployService>`_
- `Helper for accessing resources within a given Cloud Foundry space <api.html#module-cf_api.deploy_space>`_
- `Authenticated Doppler websocket client <api.html#cf_api.new_doppler>`_
- `Authenticated application instance SSH client <api.html#cf_api.SSHProxy>`_

Authenticated Cloud Controller HTTP request builder
---------------------------------------------------

The Cloud Controller API contains a great number of possible endpoints and requires OAuth2 authentication. Both of which
make a "full" implementation of the APIs challenging.

Therefore, in the interest of maintainability and conciseness, this library does *not* support a
"Python function for every endpoint" scheme, but rather provides the user an HTTP request builder object with which to
construct and send all the HTTP path, headers, parameters, etc that a given Cloud Controller endpoint requires.

Additionally, the library provides a functionality to handle the UAA OAuth2 authentication internally and return an authenticated
request builder object, from which other authenticated HTTP requests may be constructed.

Learn more `here <api.html#cf_api.new_cloud_controller>`_.

UAA OAuth2 implementations for all grant types
----------------------------------------------

The Cloud Foundry UAA endpoints support most (if not all) of the OAuth2 grant types, and this library provides two possible
ways of accessing UAA.

- A set of specially implemented functions to handle the authentication
- An HTTP request object builder alike to the Cloud Controller request object builder

The ``password``, ``authorization_code`` (including ``code`` and ``implicit``), ``client_credentials``, and ``refresh_token``
grant types are supported.

Learn more `here <api.html#cf_api.new_uaa>`_.

Support for deploying Cloud Foundry applications from an application manifest
-----------------------------------------------------------------------------

Using the Cloud Controller API request builder, this library implements most of the Cloud Foundry application manifest
YAML configuration parameters. This provides a Python interface to fully deploy (or delete) Cloud Foundry applications using the same
manifest as used with ``cf push``.

Learn more `here <api.html#module-cf_api.deploy_manifest.Deploy>`_.

Helper for deploying Cloud Foundry services
-------------------------------------------

Using the Cloud Controller API request builder, this library implements a Python interface that simplifies creating a service. This
functionality removes the tedium of looking up the service by name, looking up the plan by name, looking up the service instance by name
checking if the service exists already, and then building the request to create (or destroy) it.

Learn more `here <api.html#cf_api.deploy_service.DeployService>`_.

Helper for accessing resources within a given Cloud Foundry space
-----------------------------------------------------------------

This is a helper class that makes requests relative to a given Cloud Foundry space. This is useful when you need to interact
with a specific Cloud Foundry space and don't want to pass around space guid when searching for entities in the space
(i.e. apps, service instances, routes, etc.)

Learn more `here <api.html#module-cf_api.deploy_space>`_.

Authenticated Doppler websocket client
--------------------------------------

This provides a simple Websocket client to the Doppler API and allows handles the parsing CF protobuf log messages. This can be useful
for either monitoring application logs (i.e. ``cf logs``) or subscribing to the main loggregator firehose.

Learn more `here <api.html#cf_api.Doppler>`_.

Authenticated application instance SSH client
---------------------------------------------

This provides basic SSH authentication and a session with the shell of a Cloud Foundry application instance.

Learn more `here <api.html#cf_api.SSHProxy>`_.
