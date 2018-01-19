import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import cf_api

BASE_URL = 'http://localhost'
IS_MOCKING = False

if 'PYTHON_CF_URL' not in os.environ:
    os.environ['PYTHON_CF_URL'] = BASE_URL
    IS_MOCKING = True
if 'PYTHON_CF_CLIENT_ID' not in os.environ:
    os.environ['PYTHON_CF_CLIENT_ID'] = 'cf'
if 'PYTHON_CF_CLIENT_SECRET' not in os.environ:
    os.environ['PYTHON_CF_CLIENT_SECRET'] = ''
