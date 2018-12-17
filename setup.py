"""Setup for Publ packaging"""

# Always prefer setuptools over distutils
from setuptools import setup, find_packages
from os import path

here = path.abspath(path.dirname(__file__))

# Get the long description from the README file
with open(path.join(here, 'README.md')) as f:
    long_description = f.read()

setup(
    name='Publ',

    version='0.3.12',

    description='A content-management system for flexible web-based publishing',

    long_description=long_description,

    long_description_content_type='text/markdown',

    url='https://github.com/PlaidWeb/Publ',

    author='fluffy',
    author_email='fluffy@beesbuzz.biz',

    classifiers=[
        'Development Status :: 4 - Beta',

        'Intended Audience :: Developers',

        'Framework :: Flask',

        'License :: OSI Approved :: MIT License',

        'Natural Language :: English',

        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: 3.7',

        'Topic :: Internet :: WWW/HTTP :: Dynamic Content :: Content Management System',
        'Topic :: Internet :: WWW/HTTP :: Dynamic Content :: News/Diary',

    ],

    keywords='website cms publishing blog photogallery sharing',

    packages=['publ'],

    install_requires=[
        'Flask',
        'flask_caching',
        'arrow',
        'pony',
        'misaka',
        'Pillow',
        'pygments',
        'watchdog',
        'awesome-slugify'
    ],

    extras_require={
        'dev': ['pylint', 'twine'],
    },

    project_urls={
        'Main Site': 'http://publ.beesbuzz.biz',
        'Bug Reports': 'https://github.com/PlaidWeb/Publ/issues',
        'Funding': 'https://patreon.com/fluffy',
        'Source': 'https://github.com/PlaidWeb/Publ/',
        'Discord': 'https://discord.gg/xADP3ja'
    },

    python_requires=">=3.6",
)
