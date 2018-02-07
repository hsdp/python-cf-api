from __future__ import print_function
import os
import sys
import threading
from uuid import uuid4
from .dropsonde_util import DopplerEnvelope


class TailThread(object):
    def __init__(self, doppler, app_guid, render_log=None):
        self.ws = doppler.ws_request('apps', app_guid, 'stream')
        self.thread = threading.Thread(target=self.run)
        self.is_terminated = False

        def _render_log(msg):
            d = DopplerEnvelope.wrap(msg)
            sys.stdout.write(''.join([str(d), '\n']))
            sys.stdout.flush()

        self.render_log = render_log or _render_log

    def start(self):
        self.ws.connect()
        self.thread.start()
        return self

    def terminate(self):
        self.ws.close()
        self.thread.join()
        self.is_terminated = True
        return self

    def run(self):
        try:
            self.ws.watch(self.render_log)
        except Exception as e:
            print(e)


if __name__ == "__main__":
    import argparse
    import cf_api
    from getpass import getpass

    def main():

        args = argparse.ArgumentParser(
            description='This tool performs operations against the Cloud '
                        'Foundry Doppler logging service. It can tail a '
                        'specific application\'s logs, fetch recent logs, or '
                        'read directly from the firehose.')
        args.add_argument(
            '--cloud-controller', dest='cloud_controller', required=True,
            help='The Cloud Controller API endpoint '
                 '(excluding leading slashes)')
        args.add_argument(
            '-u', '--user', dest='user', default=None,
            help='The user used to authenticate. This may be omitted '
                 'if --client-id and --client-secret have sufficient '
                 'authorization to perform the desired operation without a '
                 'user\'s permission')
        args.add_argument(
            '-o', '--org', dest='org', default=None,
            help='The organization to be accessed')
        args.add_argument(
            '-s', '--space', dest='space', default=None,
            help='The space to be accessed')
        args.add_argument(
            '-a', '--app', dest='app', default=None,
            help='The application whose logs will be accessed')
        args.add_argument(
            '-r', '--recent', dest='recent_logs', action='store_true',
            help='Indicates to fetch the recent logs from the application')
        args.add_argument(
            '-t', '--tail', dest='tail_logs', action='store_true',
            help='Indicates to tail the logs from the application')
        args.add_argument(
            '-f', '--firehose', dest='firehose', default=None,
            help='Indicates to connect to the Cloud Foundry firehose. '
                 'The value of this option should be a unique '
                 'user-defined subscription ID that represents your logging '
                 'session. Note that you must set a custom --client-id and '
                 '--client-secret that is authorized to access the '
                 'firehose')
        args.add_argument(
            '-e', '--event-types', dest='event_types', default='',
            help='')
        args.add_argument(
            '--client-id', dest='client_id', default='cf',
            help='Used to set a custom client ID. This is required to '
                 'use the --firehose. Scope should include '
                 '`doppler.firehose\'')
        args.add_argument(
            '--client-secret', dest='client_secret', default='',
            help='Secret corresponding to --client-id')
        args.add_argument(
            '--skip-ssl', dest='skip_ssl', action='store_true',
            help='Indicates to skip SSL cert verification')
        args = args.parse_args()

        event_types = args.event_types.split(',')

        def render_log(msg):
            d = DopplerEnvelope.wrap(msg)
            if args.event_types and not d.is_event_type(*event_types):
                return
            sys.stdout.write(''.join([str(d), '\n']))
            sys.stdout.flush()

        cc = cf_api.new_cloud_controller(
            args.cloud_controller,
            username=args.user,
            password=getpass().strip() if args.user is not None else None,
            client_id=args.client_id,
            client_secret=args.client_secret,
            verify_ssl=not args.skip_ssl,
            init_doppler=True,
            refresh_token=os.getenv('CF_REFRESH_TOKEN'),
        )

        if args.firehose:
            print('*' * 40, 'firehose', '*' * 40)
            subscription_id = '-'.join([args.firehose, str(uuid4())])
            ws = cc.doppler.ws_request('firehose', subscription_id)
            try:
                ws.connect()
                ws.watch(render_log)
            except Exception as e:
                print(e)
            finally:
                ws.close()

        else:
            if not args.org or not args.space or not args.app:
                raise Exception('Org, space, and app are required')

            from . import deploy_space
            space = deploy_space.Space(
                cc,
                org_name=args.org,
                space_name=args.space,
                is_debug=True
            )

            app = space.get_app_by_name(args.app)

            if args.recent_logs:
                print('*' * 40, 'recent logs', '*' * 40)
                logs = cc.doppler.apps(app.guid, 'recentlogs').get()
                for part in logs.multipart:
                    render_log(part)

            if args.tail_logs:
                print('*' * 40, 'streaming logs', '*' * 40)
                ws = cc.doppler.ws_request('apps', app.guid, 'stream')
                try:
                    ws.connect()
                    ws.watch(render_log)
                except Exception as e:
                    print(e)
                finally:
                    ws.close()

    main()
