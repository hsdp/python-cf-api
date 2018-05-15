import os
import re
import json
import cf_api
from . import exceptions as exc

try:
    from urllib.parse import urlparse
except ImportError:
    from urlparse import urlparse

_app_to_fqdns = {}
_url_to_routes = {}
_name_to_domains = {}
_domain_to_names = {}
_url_to_app = {}
_app_to_route_fqdns = {}


def get_default_fqdn(cc, app_id=None, app_resource=None):
    """Gets the default fully qualified domain name for an application.

    Args:
        cc (cf_api.CloudController)
        app_id (str): app GUID
        app_resource (cf_api.Resource): app Resource object
    """

    if not isinstance(cc, cf_api.CloudController):
        raise exc.InvalidArgsException(
            'cc must be an instance of cf_api.CloudController', 500)

    if app_resource:
        if not isinstance(app_resource, cf_api.Resource):
            raise exc.InvalidArgsException(
                'app_resource must be an instance of cf_api.Resource', 500)
        app_id = app_resource.guid

    if not app_id:
        raise exc.InvalidStateException(
            'app_id OR app_resource is required', 500)

    if app_id in _app_to_fqdns:
        return _app_to_fqdns[app_id]

    if not app_resource:
        res = cc.apps(app_id).get()
        app_resource = res.resource

    res = cc.request(app_resource.routes_url).get()
    route = res.resource
    if not route:
        raise exc.NotFoundException(
            'No route found for app {0}'.format(app_resource.name), 404)

    res = cc.request(route['entity']['domain_url']).get()
    domain = res.resource
    if not domain:
        raise exc.NotFoundException(
            'No domain found for route {0}'.format(route['entity']['host']),
            404)

    _app_to_fqdns[app_id] = '.'.join([route['entity']['host'], domain.name])

    return _app_to_fqdns[app_id]


def get_app_fqdns(cc, app_id, use_cache=True):
    """Get all FQDNs for and app id.

    Args:
        cc (cf_api.CloudController)
        app_id (str)
        use_cache (bool)

    Returns:
         list
    """
    if not isinstance(cc, cf_api.CloudController):
        raise exc.InvalidArgsException(
            'cc must be an instance of cf_api.CloudController', 500)

    global _app_to_route_fqdns
    if app_id in _app_to_route_fqdns:
        return _app_to_route_fqdns[app_id]

    res = cc.apps(app_id, 'routes').get()
    if res.has_error:
        raise exc.ResponseException(res.text, res.response.status_code)

    fqdns = []
    for route in res.resources:
        if route.domain_guid in _domain_to_names and use_cache:
            domain = _domain_to_names[route.domain_guid]
        else:
            res = cc.request(route.domain_url).get()
            domain = res.resource
            _domain_to_names[route.domain_guid] = domain

        fqdns.append('.'.join([route.host, domain.name]))

    _app_to_route_fqdns[app_id] = fqdns

    return fqdns


def decompose_route(url):
    """Decomposes a URL into the parts relevant to looking up a route with the
    Cloud Controller.

    Args:
        url (str): some URL to an app hosted in Cloud Foundry

    Returns:
        tuple[str]: four parts, 'host', 'domain', 'port', 'path'. Note that
            'host' is the first dot-segment of the hostname and 'domain' is the
            remainder of the hostname
    """
    if not re.search('^https?://', url):
        url = '://'.join(['https', url])

    url_parts = urlparse(url)

    domain_parts = url_parts.hostname.split('.')
    if len(domain_parts) <= 2:
        raise exc.InvalidArgsException('URL does not contain a subdomain', 400)

    host, domain = domain_parts[0], '.'.join(domain_parts[1:])
    return host, domain, url_parts.port, url_parts.path


def compose_route(host, domain, port, path):
    """Builds a string representation of the route components.

    Args:
        host (str): the first dot-segment of the hostname
        domain (str): the remainder of the hostname after the first dot-segment
        port (int|str): port number if applicable. If it's a Falsy value, then
            it will be ignored
        path (str): if there's no specific path, then just set '/'

    Returns:
         str: the form is 'host.domain(:port)?/(path)?'
    """
    netloc = ['.'.join([host, domain])]
    if port:
        netloc.append(str(port))
    return '/'.join([':'.join(netloc), path])


def get_route_str(url):
    return compose_route(*decompose_route(url))


def get_route_from_url(cc, url,
                       use_cache=True,
                       ignore_path=False,
                       ignore_port=False,
                       require_one=True):
    """Gets all routes that are associated with the given URL.

    Args:
        cc (cf_api.CloudController): initialized Cloud Controller instance
        url (str): some URL to an app hosted in Cloud Foundry
        use_cache (bool): use the internal caching mechanism to speed up
            route/domain lookups
        ignore_port (bool): indicates to ignore the URL port when looking up
            the route
        ignore_path (bool): indicates to ignore the URL path when looking up
            the route
        require_one (bool): assert that there is only one route belonging to
            this URL and throw an error if there is more than one, else returns
            that one directly

    Returns:
        cf_api.Resource|list[cf_api.Resource]: If require_one=False, then a
            list is returned, else the route resource object is returned
    """
    if not isinstance(cc, cf_api.CloudController):
        raise exc.InvalidArgsException(
            'cc must be an instance of cf_api.CloudController', 500)

    host, domain, port, path = decompose_route(url)
    url = compose_route(host, domain, port, path)

    global _url_to_routes
    if url in _url_to_routes and use_cache:
        routes = _url_to_routes[url]

    else:
        global _name_to_domains
        if domain in _name_to_domains and use_cache:
            domain_guid = _name_to_domains[domain]
        else:
            res = cc.shared_domains().get_by_name(domain)
            if not res.resource:
                res = cc.private_domains().get_by_name(domain)
                if not res.resource:
                    raise exc.NotFoundException(
                        'No domain found for name {0}'.format(domain), 404)
            domain_guid = res.resource.guid
            _name_to_domains[domain] = domain_guid

        route_search = ['host', host, 'domain_guid', domain_guid]
        if not ignore_path and '/' != path:
            route_search.extend(['path', path])
        if not ignore_port and port:
            route_search.extend(['port', port])

        res = cc.routes().search(*route_search)
        if not res.resource:
            raise exc.NotFoundException(
                'No route found for host {0}'.format(host), 404)

        routes = res.resources
        if not ignore_path and not ignore_port:
            _url_to_routes[url] = routes

    if require_one:
        if len(routes) != 1:
            raise exc.InvalidStateException(
                'More than one route was found when one was required', 500)
        return routes[0]

    return routes


def get_route_apps_from_url(cc, url, use_cache=True, require_one=True,
                            started_only=True):
    """Get apps belonging to a URL hosted in Cloud Foundry. If you set
    require_one=True and start_only=False, then be aware that if there is an
    app in the STOPPED state in addition to the STARTED state attached to the
    underlying route, you'll get an exception.

    Args:
        cc (cf_api.CloudController): initialized Cloud Controller instance
        url (str): some URL to an app hosted in Cloud Foundry
        use_cache (bool): use the internal caching mechanism to speed up
            route/domain lookups
        require_one (bool): assert that there is only one app belonging to this
            URL and throw an error if there is more than one, else returns that
            one directly
        started_only (bool): indicates to limit the search to apps with the
            state of 'STARTED'

    Returns:
        cf_api.Resource|list[cf_api.Resource]: If require_one=False, then a
            list is returned, else the app resource object is returned
    """
    global _url_to_app
    url_key = get_route_str(url)

    if url_key in _url_to_app and use_cache:
        apps = _url_to_app[url_key]

    else:
        route = get_route_from_url(cc, url, use_cache=use_cache,
                                   require_one=require_one)
        res = cc.request(route.apps_url).get()
        apps = res.resources
        _url_to_app[url_key] = apps

        if started_only:
            apps = [r for r in apps if 'STARTED' == r.state]

    if require_one:
        if len(apps) != 1:
            raise exc.InvalidStateException(
                'More than one app was found when one was required', 500)
        return apps[0]

    return apps


if '__main__' == __name__:
    def main():
        import argparse
        from getpass import getpass

        args = argparse.ArgumentParser(
            description='This tool performs a reverse lookup of a Cloud '
                        'Foundry route or an application based on a given URL '
                        'belonging to that route or application. It accepts '
                        'multiple URLs and returns a JSON object with keys '
                        'corresponding to the sanitized URLs passed in and '
                        'values showing the requested routes/apps. By '
                        'default it looks up routes.')
        args.add_argument(
            '--cloud-controller', dest='cloud_controller', required=True,
            help='The Cloud Controller API endpoint '
                 '(excluding leading slashes)')
        args.add_argument(
            '-u', '--user', dest='user',
            help='The user used to authenticate. This may be omitted '
                 'if --client-id and --client-secret have sufficient '
                 'authorization to perform the desired request without a '
                 'user\'s permission')
        args.add_argument(
            '--client-id', dest='client_id', default='cf',
            help='Used to set a custom client ID')
        args.add_argument(
            '--client-secret', dest='client_secret', default='',
            help='Secret corresponding to --client-id')
        args.add_argument(
            '--skip-ssl', dest='skip_ssl', action='store_true',
            help='Indicates to skip SSL cert verification')
        args.add_argument(
            '--show-apps', dest='show_apps', action='store_true',
            help='Lookup the apps related to the given URL. '
                 'By default it looks up the routes')
        args.add_argument(
            '--ignore-path', dest='ignore_path', action='store_true',
            help='Indicates to ignore the path when looking up the app/route')
        args.add_argument(
            '--ignore-port', dest='ignore_port', action='store_true',
            help='Indicates to ignore the port when looking up the app/route')
        args.add_argument(
            '--no-require-one', dest='no_require_one', action='store_true',
            help='Indicates that there may be more than one route. By default '
                 'this tool expects one route and will throw an error if '
                 'there is more than one')
        args.add_argument(
            'url', nargs='+',
            help='URLs to be looked up to find their routes/apps')
        args = args.parse_args()

        if args.user:
            username = args.user
            password = getpass().strip()
            refresh_token = None
        else:
            username = None
            password = None
            refresh_token = os.getenv('CF_REFRESH_TOKEN')

        cc = cf_api.new_cloud_controller(
            args.cloud_controller,
            username=username,
            password=password,
            refresh_token=refresh_token,
            client_id=args.client_id,
            client_secret=args.client_secret,
            verify_ssl=not args.skip_ssl
        )

        results = {}
        for url in args.url:
            if args.show_apps:
                results[get_route_str(url)] = get_route_apps_from_url(
                    cc, url, require_one=not args.no_require_one)
            else:
                results[get_route_str(url)] = get_route_from_url(
                    cc, url,
                    ignore_path=args.ignore_path,
                    ignore_port=args.ignore_port,
                    require_one=not args.no_require_one)

        print(json.dumps(results, indent=4))

    main()
