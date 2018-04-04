# Publ

A personal publishing platform.

Like a static publishing system, only dynamic.

## Basic tenets

* Containerized web app that's deployable with little friction (hopefully)
* Do one thing (present content), do it well (hopefully)
* Use external tools for site content editing
* Be CDN-friendly
* High-DPI images and image sets as first-class citizens

## See it in action

The main site, which is also (presently) what's distributed along with the
code, is at http://publ.beesbuzz.biz/

It is of course a work in progress!

## Operating requirements

I am designing this to work in any WSGI-capable environment with Python 3. This
means that it will, for example, be deployable on any shared hosting which
has Passenger support (such as Dreamhost), as well as on Heroku, Google AppEngine,
S3, or any other simple containerized deployment target that can pull data from
the ground-truth content store (which could very well be git).

Since the filesystem itself is the ground truth for content, the database
requirements are minimal; the database will only exist as an index to the
files, really. I expect the default of in-process/in-memory sqlite
to be sufficient for most sites, and larger sites can do a file-backed sqlite
store. Really large-scale deployments could use MySQL or Postgres or whatever.
For prototyping I expect to use [Peewee](https://peewee.readthedocs.io/en/latest/)
as the ORM but eventualy I might move to SQLAlchemy or the like. Who knows!

## Supporting Publ development

Please consider supporting me on [Patreon](http://patreon.com/fluffy)
or [Liberapay](https://liberapay.com/fluffy).
