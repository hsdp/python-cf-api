"""Log with UAA web login page (using grant_type "authorization_code")

The use case for this grant type is for websites that want to
"Log in with UAA".

This example is more of snippets, since it requires redirecting to UAA and
then receiving the authorization code on your web server...
"""
from __future__ import print_function
import os
import sys
import json
import cf_api
from webbrowser import open_new
from BaseHTTPServer import HTTPServer, BaseHTTPRequestHandler


PORT = int(os.getenv('PORT', 8080))


def browser_authorize(auth_uri):
    """Opens the UAA login page in the default web browser to allow the user
    to login, then waits for UAA to redirect back to http://localhost:8080,
    and then, then captures the authorization code and verifies it with UAA,
    and finally displays the login info.
    """

    # open the UAA login page in the web browser
    open_new(auth_uri)

    class CodeHandler(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.send_header('Content-Type', 'text/html')
            self.end_headers()
            self.wfile.write("""
                <html><head>
                <script>window.onload = function() {window.close();}</script>
                </head><body>
                Hi... and bye! (you may close this window)</body>
                </html>
            """)
            parts = self.path.split('=')
            if len(parts) < 2:
                raise Exception('invalid response {0}'.format(self.path))
            auth_code = parts[1]
            self.server.result = auth_code

    # create a server to handle the redirected authorization code from UAA
    server = HTTPServer(('', PORT), CodeHandler)

    # this method waits for a single HTTP request and then shuts down the
    # server
    server.handle_request()

    return server.result


print('----------')
cloud_controller_url = raw_input('cloud controller url: ').strip()
client_id = 'test-client-id'
client_secret = 'test-client-secret'

print('----------')
print('Redirecting to UAA...')
# we create an instance of the cloud controller, but tell it to NOT authorize
# with UAA.
cc_noauth = cf_api.new_cloud_controller(
    cloud_controller_url,
    client_id=client_id,
    client_secret=client_secret,
    no_auth=True
)

# we use noauth client to create the redirect URI
uaa_uri = cc_noauth.uaa.authorization_code_url('code')

# get the authorization code by logging in at the web browser, receiving
# the redirect, and extracting the authorization code
code = browser_authorize(uaa_uri)
print('authorization code: ' + str(code))

print('----------')
print('Verifying authorization code...')
# we create a UAA authenticated client using the authorization code by passing
# in the "authorization_code" keyword argument
cc = cf_api.new_cloud_controller(
    cloud_controller_url,
    client_id=client_id,
    client_secret=client_secret,
    authorization_code=dict(
        code=code,
        response_type='code',
    )
)
print('Login OK!')

print('----------')
access_token = cc.uaa.get_access_token()
refresh_token = cc.uaa.get_refresh_token()
print('access_token: ' + access_token.to_string() + '\n')
print('refresh_token: ' + refresh_token.to_string() + '\n')
print('user_id: ' + access_token.user_id + '\n')
print('user_name: ' + access_token.user_name + '\n')
print('access_token_data:')
json.dump(access_token.attrs, sys.stdout, indent=2)
print()
