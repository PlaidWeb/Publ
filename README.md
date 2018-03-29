# Publ

A personal publishing platform. Work in progress, nothing much to see here yet.

## Basic tenets

* Containerized web app that's deployable with little friction (hopefully)
* As little friction as possible to post
* Do one thing (present content), do it well (hopefully)
* Use external tools for site content editing
* Be CDN-friendly
* High-DPI images and image sets as first-class citizens

## Design

The "ground truth" store of the site content will be in the filesystem. Editing
content will be in the form of editing files. This allows for external tools that
let content authors interact with the content in whatever way they see fit; they
could use their favorite local editor over sshfs or attach an external tool such
as CodeAnywhere, they could put it into a git repository and pull it onto the
server, content could be pulled in via cron job (RSS/atom syndication!), or any
other number of things could happen.

(As a very long-term goal I might be convinced to make a post editor that works
with Publ directly, with the intention of making it even easier for non-technical
users. But my hope is that this is easy enough to support for other tools that
an ecosystem might spring up around it.)

Site content is to be controlled by templates. Templates inherit from the
parent directory. Site sections are set up via directories, for that matter.

Items will have a GUID associated with them. GUIDs will automatically track
between directories; want to restructure/move content? That's okay, any
inbound permalinks will automatically redirect to the new canonical location.

Categories are assigned simply based on which directory the content is in.
Items will have further tagging on them. Items can also have whatever arbitrary
header data associated with them.

On that note, a content item is an RFC2822-style "message," which will look
something like this:

    Date: 2017/1/2 3:45:06
    Author: fluffy
    Title: This is some test content
    ID: 123456
    Tags: test blog hello

    This is the top text of the post.

    This is the second paragraph of top text. But wait, there's more!

    ~~~~~

    This is the stuff below the cut.

    This is all written in Markdown; hello *happy campers*, so *squishy* to
    *smell* you!

I intend for there to be standard headers for all the useful things for a blog,
including the ability to reference other entries (i.e. reblogs/commentary).

The templating system is simply Jinja2.

URL schemas are going to be something like:

* `http://publ.example.com/some/category/whatever/` -- renders the `index`
  template that maps to the `some/category/whatever` category
* `http://publ.example.com/some/category/feed` -- renders the `feed` template
* `http://publ.example.com/category/12345-this-is-some-test-content` -- renders
  the specified content
    * content URLs only care about the numeric ID; if the SEO text mismatches/is
      missing/etc, or the category is wrong, this will result in a 301 redirect
      to the correct canonical URL

Entries will be mapped to the `entry` template type, which will receive the
category and entry as template parameters. Other templates will just get the
category as a template parameter; the category will have options for querying
entries within the current category as well as any subcategories. The view of
entries will also default to being constrained by the query parameters (which
will make it easy to support pagination, date-based archives, JSON views for
dynamic loading, etc.)

Image rendering will be configurable by the template and exposed by some custom
Markdown entities; I haven't yet designed what those entities will look like
but the configuration will be things like image scaling (for `<img srcset>`)
and cropping (for auto-excerpting in comic RSS feeds, for example), as well as
the ability to provide multiple images with `title` attributes. The template
rendering system will ensure that the right renditions are available, and
provide a URL to the rendered content. Which could even end up in an external
CDN, such as Cloudflare.

### Implications

This is basically acting in the UNIX philosophy; it's a frontend that reformats
UNIX-filesystem-based content for the web. Want a group blog? Let other people
write into the content store (via a shared git repo, or filesystem permissions
on your mounted drive, or whatever).

By keeping templates and content separate, this allows for easier deployment
and sharing of stock templates and site designs. And these can also be pulled
in via whatever arbitrarily-complex git mappins you want, for example.

This also means that you can stage your site in multiple places, or you can
work on your templates separately from your content, or you can spin up a local
instance to preview changes to things, or whatever else you want. No more having
to worry about the state of your database or having a bad template change break
everything. And if you're using git, you have undo for free!

Want to change some of your templates temporarily for a holiday? Make a branch
and pull that. Switch back to your usual branch when you're done. And so on.

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

## Design, roadmap, etc

please see the [project wiki](https://github.com/fluffy-critter/Publ/wiki/Roadmap)

## Supporting Publ development

Please consider supporting me on  [Patreon](http://patreon.com/fluffy) or [Liberapay](https://liberapay.com/fluffy).
