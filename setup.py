"""Setup for Publ packaging"""

from distutils.util import convert_path
from os import path

# Always prefer setuptools over distutils
from setuptools import find_packages, setup

here = path.abspath(path.dirname(__file__))

# Get the long description from the README file
with open(path.join(here, 'README.md')) as f:
    long_description = f.read()

main_ns = {}
ver_path = convert_path('publ/__version__.py')
with open(ver_path) as ver_file:
    exec(ver_file.read(), main_ns)


setup(
    name='Publ',

    version=main_ns['__version__'],

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
        'Programming Language :: Python :: 3.5',
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: 3.7',
        'Programming Language :: Python :: 3.8',

        'Topic :: Internet :: WWW/HTTP :: Dynamic Content :: Content Management System',
        'Topic :: Internet :: WWW/HTTP :: Dynamic Content :: News/Diary',

    ],

    keywords='website cms publishing blog photogallery sharing',

    packages=find_packages(),
    package_data={'publ': ['default_template/*']},

    install_requires=[
        'arrow',
        'atomicwrites',
        'authl>=0.3.1',
        'awesome-slugify',
        'flask',
        'flask_caching',
        'misaka',
        'pillow',
        'pony>=0.7.11',
        'pygments',
        'watchdog',
    ],

    extras_require={'dev': [
        'autopep8',
        'flake8',
        'isort',
        'mypy',
        'pylint',
        'twine',
    ]},

    project_urls={
        'Main Site': 'http://publ.beesbuzz.biz',
        'Bug Reports': 'https://github.com/PlaidWeb/Publ/issues',
        'Source': 'https://github.com/PlaidWeb/Publ/',
        'Discord': 'https://beesbuzz.biz/discord',
        'Funding': 'https://liberapay.com/PlaidWeb'
    },

    python_requires=">=3.5",
)
