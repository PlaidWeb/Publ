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
