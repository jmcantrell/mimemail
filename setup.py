#!/usr/bin/env python

from setuptools import setup, find_packages
from glob import glob

setup(
        name='MIMEMail',
        version='0.2.12',
        description='Command line MUA using the MIME message format.',
        author='Jeremy Cantrell',
        author_email='jmcantrell@gmail.com',
        classifiers=[
            'Development Status :: 4 - Beta',
            'Environment :: Console',
            'Intended Audience :: System Administrators',
            'License :: OSI Approved :: GNU General Public License (GPL)',
            'Natural Language :: English',
            'Operating System :: OS Independent',
            'Programming Language :: Python',
            'Topic :: Communications :: Email :: Email Clients (MUA)',
            'Topic :: System :: Systems Administration',
            'Topic :: Utilities',
            ],
        install_requires=[
            'ScriptUtils',
            ],
        entry_points={
            'console_scripts': [
                'mimemail=mimemail:main',
                ]
            },
        py_modules=[
            'mimemail',
            ],
        )
