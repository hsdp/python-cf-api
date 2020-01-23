import os
import six
import json
import time
import jwt
import responses
from requests_factory import RequestFactory
from uuid import uuid4

cc_api_url = os.getenv('CC_API_URL', 'http://localhost')
uaa_api_url = os.getenv('UAA_API_URL', 'http://localhost')


relations_tree = {
    'apps': [
        'routes',
        'summary',
        'service_bindings',
        'env',
        'permissions',
        'instances',
        'restage',
    ],
    'buildpacks': [
        'bits',
    ],
    'domains': [
        'spaces'
    ],
    'events': [],
    'info': [],
    'jobs': [],
    'quota_definitions': [],
    'organizations': [
        'auditors',
        'billing_managers',
        'managers',
        'private_domains',
        'users',
        'domains',
        'services',
        'space_quota_definitions',
        'spaces',
        'instance_usage',
        'memory_usage',
        'user_roles',
    ],
    'private_domains': [
        'shared_organizations'
    ],
    'resource_match': [],
    'routes': [
        'apps',
        'route_mappings',
    ],
    'routes/reserved/domain': [
        'host',
    ],
    'route_mappings': [],
    'config/running_security_groups': [],
    'config/staging_security_groups': [],
    'security_groups': [
        'spaces',
        'staging_spaces',
    ],
    'service_bindings': [],
    'service_brokers': [],
    'service_instances': [
        'routes',
        'service_bindings',
        'service_keys',
        'permissions',
    ],
    'service_keys': [],
    'service_plan_visibilities': [],
    'service_plan': [
        'service_instances',
    ],
    'services': [
        'service_plans',
    ],
    'shared_domains': [],
    'space_quota_definitions': [
        'spaces'
    ],
    'spaces': [
        'auditors',
        'developers',
        'managers',
        'security_groups',
        'staging_security_groups',
        'unmapped_routes',
        'summary',
        'apps',
        'auditors',
        'developers',
        'domains',
        'events',
        'routes',
        'security_groups',
        'staging_security_groups',
        'service_instances',
        'services',
        'user_roles',
    ],
    'stacks': [],
    'users': [
        'audited_organizations',
        'audited_spaces',
        'billing_managed_organizations',
        'managed_organizations',
        'managed_spaces',
        'organizations',
    ],
}

relations_tree_v3 = {
    'apps': {
        'relationships': [
            'space',
        ],
        'links': [
            'space',
            'processes',
            'packages',
            'route_mappings',
            'environment_variables',
            'droplets',
            'tasks',
        ]
    },
    'builds': {
        'toplevel': [
            'package',
            'droplet',
        ],
        'links': [
            'build',
            'app',
        ],
    },
    'buildpacks': {
        'links': [
            'upload',
        ]
    },
    'domains': {
        'relationships': [
            'organizations',
        ],
        'links': [
            'organization',
        ],
    },
    'droplets': {
        'links': [
            'package',
            'app',
        ]
    },
    'isolation_segments': {
        'links': [
            'organizations',
        ],
    },
    'jobs': {},
    'organizations': {
        'links': [
            'domains',
        ],
    },
    'packages': {},
    'processes': {
        'relationships': [
            'app',
            'revision',
        ],
        'links': [
            'app',
            'space',
            'stats'
        ]
    },
    'routes': {
        'relationships': [
            'space',
            'domain',
        ],
        'links': [
            'space',
            'domain',
            'destinations',
        ],
    },
    'service_instances': {
        'relationships': [
            'space',
        ],
        'links': [
            'space',
        ],
    },
    'spaces': {
        'relationships': [
            'organization',
        ],
        'links': [
            'organization',
        ],
    },
    'stacks': {},
    'tasks': {
        'relationships': [
            'app',
        ],
        'links': [
            'app',
            'droplet',
        ],
    },
}


cc_v2_info = {
    "token_endpoint": uaa_api_url,
    "app_ssh_endpoint": "ssh.cf.com:2222",
    "app_ssh_host_key_fingerprint": "00:00:00:00:00:00:00:00:00:00:00:00:00:00:00:00",
    "app_ssh_oauth_client": "ssh-client-id",
    "doppler_logging_endpoint": "wss://doppler.cf.com:4443"
}


uaa_oauth_token = {
    'access_token': 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJmb28iLCJ1c2VyX2lkIjoiMmIxNjM0MzctM2VkZC00ZDEwLTgwOGItNDRmZDIzODJhOTU4IiwiZXhwIjoxOTkxODY1ODQxfQ.SMrHg7o9Mv9_hT8GIrG8Rao5CPHumnOPO-KWD8BRz4k',
    'refresh_token': 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJmb28iLCJ1c2VyX2lkIjoiMmIxNjM0MzctM2VkZC00ZDEwLTgwOGItNDRmZDIzODJhOTU4IiwiZXhwIjoxOTkxODY1ODQxfQ.SMrHg7o9Mv9_hT8GIrG8Rao5CPHumnOPO-KWD8BRz4k',
}


def make_uaa_oauth_token(ttl):
    secret = str(uuid4())
    payload = {
        'iss': 'foo',
        'exp': int(time.time() + ttl),
        'user_id': str(uuid4()),
    }
    atoken = six.text_type(jwt.encode(payload, secret, algorithm='HS256'), 'utf-8')
    rtoken = six.text_type(jwt.encode(payload, secret, algorithm='HS256'), 'utf-8')
    return {
        'access_token': atoken,
        'refresh_token': rtoken,
    }


def make_response(version, endpoint):
    if version == 3:
        return make_response_v3(version, endpoint)
    else:
        return make_response_v2(version, endpoint)


def make_response_v2(version, endpoint):
    uuid = str(uuid4())
    version = 'v' + str(version)
    name = 'my-name-' + uuid
    entity = {
        'name': name,
        'host': name,
        'label': name,
        'status': 'STARTED',
    }
    for relation in relations_tree[endpoint]:
        if relation.endswith('s'):
            relation_ = relation[:-1]
        entity[relation_ + '_guid'] = str(uuid4())
        entity[relation + '_url'] = '/'.join([
            cc_api_url, version, endpoint, uuid, relation])
    res = {
        'metadata': {
            'guid': uuid,
            'url': '/'.join([cc_api_url, version, endpoint, uuid])
        },
        'entity': entity
    }
    return res


def make_response_v3(version, endpoint):
    uuid = str(uuid4())
    version = 'v' + str(version)
    name = 'my-name-' + uuid
    res = {
        'guid': uuid,
        'name': name,
        'state': 'STARTED',
        'stack': 'my-stack',
        'relationships': {},
        'links': {
            'self': {
                'href': '/'.join([cc_api_url, version, endpoint, uuid]),
            },
        },
    }
    for relation in relations_tree_v3[endpoint]['links']:
        if relation.endswith('s') and not relation.endswith('ss'):
            link = '/'.join([cc_api_url, version, endpoint, uuid, relation])
        else:
            link = '/'.join([cc_api_url, version, relation + 's', uuid])
        res['links'][relation] = {'href': link}
    for relation in relations_tree_v3[endpoint]['relationships']:
        res['relationships'][relation] = {'data': {'guid': uuid}}
    return res


def make_response_list(version, endpoint, n, **extras):
    res = {
        'resources': [
            make_response(version, endpoint)
            for i in range(n)
        ]
    }
    res.update(extras)
    return res


def make_error(version, status):
    if version == 3:
        return {
            'errors': [
                {
                    'code': status,
                    'title': 'CF-ErrorCode',
                    'detail': 'an error occurred ({0})'.format(status)
                }
            ],
        }
    else:
        return {
            'error_code': str(status),
            'error_description': 'an error occurred ({0})'.format(status),
        }


def prepare_request(cc, method, endpoint, guid1=None, relation=None, guid2=None, status=200, version=2, n=1, body=None, next_url_path=None):
    url = [endpoint]
    if status < 200 or status >= 300:
        res = make_error(version, status)
    elif body:
        res = body
    elif guid1 is None and relation is None and guid2 is None:
        res = make_response_list(version, endpoint, n)
    elif guid1 is not None and relation is not None and guid2 is None:
        url.extend([guid1, relation])
        res = make_response_list(version, endpoint, n)
    elif guid1 is not None and relation is None and guid2 is None:
        url.append(guid1)
        res = make_response(version, endpoint)
    elif guid1 is not None and relation is not None and guid2 is not None:
        url.extend([guid1, relation, guid2])
        res = make_response(version, endpoint)
    else:
        raise Exception('invalid arguments')
    if next_url_path is not None:
        if version == 3:
            res['pagination'] = {
                'next': {
                    'href': '/'.join([cc_api_url, next_url_path])
                }
            }
        else:
            res['next_url'] = next_url_path
    if isinstance(cc, RequestFactory):
        req = cc.request(*url).set_method(method)
        responses.add(method.upper(), req.base_url, body=json.dumps(res), status=status)
        return req
    else:
        if version is not None:
            url.insert(0, 'v' + str(version))
        url.insert(0, cc)
        url = '/'.join(url)
        responses.add(method.upper(), url, body=json.dumps(res), status=status)
        return None

