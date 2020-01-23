from setuptools import setup
from os import path

with open(path.join(path.dirname(__file__), 'requirements.txt')) as f:
    reqs = [l for l in f.read().strip().split('\n') if not l.startswith('-')]

with open(path.join(path.dirname(__file__), 'version.txt')) as f:
    __version__ = f.read().strip()

setup(
    name='cf_api',
    version=__version__,
    description='Python Interface for Cloud Foundry APIs',
    long_description=open('README.md').read(),
    long_description_content_type="text/markdown",
    license='Apache License Version 2.0',
    author='Adam Jaso',
    author_email='ajaso@hsdp.io',
    packages=['cf_api'],
    package_dir={
        'cf_api': 'cf_api',
    },
    install_requires=reqs,
    url='https://github.com/hsdp/python-cf-api',
)
