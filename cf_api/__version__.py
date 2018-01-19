import re, os
with open(os.path.join(os.path.dirname(__file__), '../version.txt')) as f:
    __version__ = f.read().strip()
__semver__ = re.split('[ab]', __version__, 1)[0]
