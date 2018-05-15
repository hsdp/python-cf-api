from __future__ import print_function
import os
from paramiko import SSHClient
from paramiko.client import MissingHostKeyPolicy
from . import exceptions as exc
import cf_api


class ProxyPolicy(MissingHostKeyPolicy):
    def __init__(self, *args, **kwargs):
        proxy = kwargs['proxy']
        del kwargs['proxy']
        super(ProxyPolicy, self).__init__(*args, **kwargs)
        self.fingerprint = proxy.fingerprint
        if 22 != proxy.port:
            self.host = ''.join(['[', proxy.host, ']:', str(proxy.port)])
        else:
            self.host = proxy.host

    def missing_host_key(self, client, hostname, key):
        fingerprint = ':'.join([
            '{0:#0{1}x}'.format(i, 4).replace('0x', '')
            for i in list(bytearray(key.get_fingerprint()))])
        if self.host == hostname and self.fingerprint == fingerprint:
            return True
        raise Exception('Unknown host key fingerprint')


class SSHSession(object):
    def __init__(self, ssh_proxy, app_guid, instance_index, password=None):
        self.ssh_proxy = ssh_proxy
        self.app_guid = app_guid
        self.instance_index = instance_index
        self.password = password
        self.client = SSHClient()
        self.client.set_missing_host_key_policy(ProxyPolicy(proxy=ssh_proxy))

    @property
    def username(self):
        return ''.join(['cf:', str(self.app_guid),
                        '/', str(self.instance_index)])

    def authenticate(self):
        self.password = self.ssh_proxy.uaa.one_time_password(
            self.ssh_proxy.client_id)
        return self

    def open(self, **kwargs):
        if self.password is None:
            raise exc.InvalidStateException(
                'Can\'t open ssh session without a password. '
                'Please authenticate first.')
        kwargs['username'] = self.username
        kwargs['password'] = self.password
        kwargs['port'] = self.ssh_proxy.port
        self.client.connect(
            self.ssh_proxy.host,
            **kwargs
        )

    def close(self):
        self.client.close()

    def execute(self, command):
        return self.client.exec_command(command)


if '__main__' == __name__:
    def main():
        import sys
        import argparse

        args = argparse.ArgumentParser()
        args.add_argument('--cloud-controller', required=True)
        args.add_argument('--guid', required=True)
        args.add_argument('-i', dest='index', required=True)
        args.add_argument('-c', '--command', dest='command', required=True)
        args.add_argument('--stderr', action='store_true', required=False)
        args = args.parse_args()
        rt = os.getenv('CF_REFRESH_TOKEN')
        cc = cf_api.new_cloud_controller(
            args.cloud_controller,
            refresh_token=rt,
            client_id='cf',
            client_secret=''
        )
        ssh = SSHSession(cc.ssh_proxy, args.guid, args.index)
        ssh.authenticate()

        try:
            ssh.open(allow_agent=False, look_for_keys=False)
            si, so, se = ssh.execute(args.command)
            for line in so:
                sys.stdout.write(line)
            if args.stderr:
                for line in se:
                    sys.stderr.write(line)
        finally:
            ssh.close()

    main()
