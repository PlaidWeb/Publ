# Publ

A personal publishing platform. Like a static publishing system, only dynamic.

## Motivation

I make a lot of different things — comics, music, art, code, games — and none of
the existing content management systems I found quite satisfy my use cases.
Either they don't allow enough flexibility in the sorts of content that they can
provide, or the complexity in managing the content makes it more complicated than
simply hand-authoring a site.

I want to bring the best of the classic static web to a more dynamic publishing
system; scheduled posts, category-based templates, and built-in support for
image renditions (including thumbnails, high-DPI support, and image galleries).
And I want to do it all using simple Markdown files organized in a sensible
file hierarchy.

## Basic tenets

* Containerized web app that's deployable with little friction (hopefully)
* Do one thing (present heterogeneous content), do it well (hopefully)
* Use external tools for site content editing
* Be CDN-friendly
* High-DPI images and image sets as first-class citizens
* Interoperate with everything that's open for interoperation (especially [IndieWeb](http://indieweb.org))

## See it in action

The main demonstration site is at http://publ.beesbuzz.biz/ — it is of course a
work in progress!

## Operating requirements

I am designing this to work in any WSGI-capable environment with Python 3. This
means that it will, for example, be deployable on any shared hosting which
has Passenger support (such as Dreamhost), as well as on Heroku, Google AppEngine,
S3, or any other simple containerized deployment target.

The file system is the ground truth for all site data, and while it does use a
database as a content index, the actual choice of database shouldn't matter all
that much. I am targeting SQLite for development, but mysql and Postgres should
be supported as well.

## Additional resources

The [Publ-site](https://github.com/PlaidWeb/Publ-site) repository stores all of the templates, site content, and configuration for the [Publ site](http://publ.beesbuzz.biz).

The [Publ-templates-beesbuzz.biz](https://github.com/PlaidWeb/Publ-templates-beesbuzz.biz) repository provides a stripped-down sample site based on [my personal homepage](http://beesbuzz.biz).

## Authors

In order of first contribution:

* [fluffy](https://github.com/fluffy-critter)
* [karinassuni](https://github.com/karinassuni)
