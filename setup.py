#!/usr/bin/env python

import re
import codecs
import os

# Prevent spurious errors during `python setup.py test`, a la
# http://www.eby-sarna.com/pipermail/peak/2010-May/003357.html:
try:
    import multiprocessing
except ImportError:
    pass


from setuptools import setup


def read(*parts):
    return codecs.open(os.path.join(os.path.dirname(__file__), *parts)).read()


def find_version(*file_paths):
    version_file = read(*file_paths)
    version_match = re.search(r"^__version__ = ['\"]([^'\"]*)['\"]",
                              version_file, re.M)
    if version_match:
        return version_match.group(1)
    raise RuntimeError('Unable to find version string.')


def find_install_requires():
    return [x.strip() for x in
            read('requirements.txt').splitlines()
            if x.strip() and not x.startswith('#')]


def find_tests_require():
    return [x.strip() for x in
            read('test-requirements.txt').splitlines()
            if x.strip() and not x.startswith('#')]


try:
    import pypandoc
    README = pypandoc.convert('README.md', 'rst')
except (IOError, ImportError, OSError, RuntimeError) as x:
    import sys
    print >> sys.stderr, "Unable to convert README.md to reStructuredText"
    print >> sys.stderr, sys.exc_info()[0]
    print >> sys.stderr, x
    README = read('README.md')


setup(
    name='crontabber',
    entry_points={
        'console_scripts': ['crontabber = crontabber.app:local_main']
    },
    version=find_version('crontabber', '__init__.py'),
    url='https://github.com/mozilla/crontabber',
    author='Peter Bengtsson',
    author_email='peterbe@mozilla.com',
    description="A cron job runner with self-healing and job dependencies.",
    long_description=README,
    packages=['crontabber', 'crontabber.tests'],
    include_package_data=True,
    install_requires=find_install_requires(),
    zip_safe=False,
    classifiers=[
        'Development Status :: 4 - Beta',
        'License :: OSI Approved :: Mozilla Public License 2.0 (MPL 2.0)',
        'Operating System :: OS Independent',
        'Programming Language :: Python :: 2.6',
        'Programming Language :: Python :: 2.7',
        'Topic :: Software Development :: Libraries :: Python Modules',
    ],
    test_suite='crontabber.tests',
    tests_require=find_tests_require(),
)
