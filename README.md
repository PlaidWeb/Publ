# Publ

A personal publishing platform. Like a static publishing system, only dynamic.

## Motivation

I make a lot of different things — comics, music, art, code, games — and none of
the existing content management systems I found quite satisfied my use cases.
Either they don't allow enough flexibility in the sorts of content that they can
provide, or the complexity in managing the content makes it more complicated than
simply hand-authoring a site.

I wanted to bring the best of the classic static web to a more dynamic
publishing system; scheduled posts, private posts, category-based templates, and
built-in support for image renditions (including thumbnails, high-DPI support,
and image galleries). And I want to do it all using simple Markdown files
organized in a sensible file hierarchy.

## Basic tenets

* Containerized web app that's deployable with little friction (hopefully)
* Do one thing (present heterogeneous content), do it well (hopefully)
* Use external tools for site content editing
* Be CDN-friendly
* High-DPI images and image sets as first-class citizens
* Interoperate with everything that's open for interoperation (especially [IndieWeb](http://indieweb.org))

## See it in action

The main demonstration site is at https://beesbuzz.biz/ — it is of course a
work in progress! The documentation site for Publ itself (which is also a work in progress) lives at https://publ.plaidweb.site/

## Operating requirements

I am designing this to work in any WSGI-capable environment with a supported
version of Python. This means that it will, for example, be deployable on any
shared hosting which has Passenger support (such as Dreamhost), as well as on
Heroku, Google AppEngine, S3, or any other simple containerized deployment
target.

The file system is the ground truth for all site data, and while it does use a
database as a content index, the actual choice of database doesn't matter all
that much. A typical deployment will use SQLite, but MySQL, Postgres, Oracle,
and Cockroach are also supported.

## Developing Publ

In order to develop Publ itself, you'll need to install its dependencies; see
the [getting started
guide](http://publ.plaidweb.site/manual/328-Getting-started) for more
information. In particular, make sure you have compatible versions of
[Python](https://python.org/) and [Poetry](https://python-poetry.org/)
installed, and, if on Windows, you'll probably need to install the [Visual C++
build tools](https://visualstudio.microsoft.com/downloads/).

As far as developing Publ itself goes, cloning this repository and running
`./runTests.sh` (Linux/macOS/etc.) or `wintests.cmd` (Windows) should get you up
and running. The runtime manual test suite site lives in `tests/` (with the
actual site content in `content/`, `templates/` and `static/`).

For developing CLI functionality, you'll have to override the `FLASK_APP`
environment variable to be `test_app.py`.

## Additional resources

The [Publ-site](https://github.com/PlaidWeb/Publ-site) repository stores all of
the templates, site content, and configuration for the [Publ
site](https://publ.plaidweb.site).

The
[Publ-templates-beesbuzz.biz](https://github.com/PlaidWeb/Publ-templates-beesbuzz.biz)
repository provides a stripped-down sample site based on [my personal
homepage](https://beesbuzz.biz).

## Authors

In order of first contribution:

* [fluffy](https://github.com/fluffy-critter)
* [karinassuni](https://github.com/karinassuni)
