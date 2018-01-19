from __future__ import print_function
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import cf_api
import pkgutil
import inspect
import requests
import unittest
from unittest import TestCase
from unittest import TestSuite


def run_test_case(runner, test_case_class):
    suite = TestSuite()
    for method in dir(test_case_class):
        if method.startswith('test_'):
            suite.addTest(test_case_class(method))
    runner.run(suite)


if '__main__' == __name__:
    def main():
        runner = unittest.TextTestRunner(verbosity=2)
        tests_dir, _ = os.path.split(__file__)
        for module, name, ispkg in pkgutil.iter_modules(tests_dir):
            mod = module.find_module(name).load_module(name) 
            for clskey in dir(mod):
                cls = getattr(mod, clskey)
                if inspect.isclass(cls) and clskey.startswith('Test'):
                    run_test_case(runner, cls)


    main()
