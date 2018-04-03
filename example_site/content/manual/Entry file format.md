Title: Entry file format
Date: 2018-04-02 14:04:32-07:00
Entry-ID: 322
UUID: 9b03da44-da6a-46a7-893a-d4ecbe813681
Path-Alias: /entry-format

## Overall format

Publ entries are files saved as `.md` or `.html` in your content directory. An
entry consists of three parts: Headers, above-the-fold, and below-the-fold (also
known as a "cut").

Here is what an entry might look like:

    Title: My first blog entry
    Date: 2018/01/04 12:34PM
    Category: /blog/random

    Hi, this is my first blog entry. I guess I don't have a lot to say.

    ~~~~~

    Well, maybe a *little* more.


## Headers

Headers are, more or less, a series of lines like:

    Header-Name: Header-Value
    Another-Header-Name: Header-Value

followed by a blank line. You can define whatever headers you want for your
templates; the following headers are what Publ itself uses:

* **`Title`**: The title of the entry

    If none is given, it will try to infer the title from the filename. It will
    probably get this wrong.

* **`Entry-ID`**: The numerical ID of the entry

    This must be unique across all
    entries and will be automatically assigned if missing. It must also be just
    a number.

    Entry IDs also provide a convenient linking mechanism; this entry has ID of 322 so
    [a link to /322](/322) or [322](322) works fine regardless of where the
    entry gets moved to in the future.

* **`Date`**: The publication date and time

    This can be in any
    format that [Arrow](http://arrow.readthedocs.io) understands. If no timezone
    is specified it will use the timezone indicated in `config.py`.

    **Default value**: the creation time of the entry (and will be added to the
    file for later).

* **`Category`**: Which category to put this entry in

    **Default value:** the entry file's directory

* **`Status`**: The publish status of the entry

    Allowed values:

    * `DRAFT`: This entry is not visible at all
    * `HIDDEN`: This entry is visible, but will not be shown in entry lists
    * `PUBLISHED`: This entry is visible at all times
    * `SCHEDULED`: Until the publication date, this acts as `HIDDEN`; afterwards, it acts as `PUBLISHED`

    **Default value:** `SCHEDULED`

* **`Type`**: The sort of entry that this is

    Allowed values:

    * `ENTRY`: A normal entry that exists within the flow of time
    * `PAGE`: An entry that represents a static page

    **Default value:** `ENTRY`

    **Note**: In the future this will probably be deprecated in favor of the tagging system

* **`Slug-Text`**: The human-readable part of the URL

    In some circles this is known as "SEO text."

    **Default value:** the entry title if not present, or to the entry's filename (minus extension) if there's no title.

* **`Redirect-URL`**: A URL to redirect this entry to

    This is useful if you want to remove an entry and redirect to another entry, or if
    you want an entry to be a placeholder for some external content (e.g. when the entry
    was syndicated from an external source).

    This will also override the entry's permalink.

* **`Path-Alias`**: An alternate path to this entry

    This is useful for redirecting old, non-Publ URLs to this entry. For example,
    if you're migrating from a legacy site and you have a URL like `http://example.com/blog/0012345.php`
    you can set a header like:

        Path-Alias: /blog/0012345.php

    Any number of these may be added to any given URL.

    For example, this entry has a `Path-Alias` of [`/entry-format`](/entry-format).

    **Note:** A path-alias will never override another entry at its canonical URL;
    however, it can potentially override any other kind of URL, including URLs for
    category views and non-canonical entry URLs.

* **`Path-Unalias`**: Remove an old path alias

    If you accidentally set a path-alias or want to remove it, rather than just deleting
    the `Path-Alias` header you should change it to a `Path-Unalias` (or add that header to
    another entry). This way you can ensure that the path alias will be removed from the
    index.

        Path-Unalias: /some/old/url/5-oops

* **`UUID`**: A globally-unique identifier for the entry

    While Publ doesn't use this for itself, having this sort of generated ID is
    useful for Atom feeds and the like. As such, it will be automatically generated if not present.

    It is *highly recommended* that this be unique across all entries.

## Entry content

After the headers, you can have entry content; if the file has a `.htm` or `.html`
extension it will just render as plain HTML, but with a `.md` extension it will
render as [Markdown](https://en.wikipedia.org/wiki/Markdown).

Publ supports the standard Markdown syntax (as provided by the [Python reference
implementation](https://python-markdown.github.io)). The plan is to eventually
add support for [GitHub-flavored markdown](https://guides.github.com/features/mastering-markdown/),
as well as some Publ-specific tags for things like cuts, image renditions, and galleries.

### Custom tags

* **`~~~~~`**: Indicates the cut from above-the-fold to below-the-fold content (must be on a line by itself)
