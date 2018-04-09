Title: Entry file format
Date: 2018-04-02 14:04:32-07:00
Entry-ID: 322
UUID: 9b03da44-da6a-46a7-893a-d4ecbe813681
Path-Alias: /entry-format

A guide to writing page content for Publ

.....

## Overall format

Publ entries are files saved as `.md` or `.html` in your content directory. An
entry consists of three parts: Headers, above-the-fold, and below-the-fold (also
known as a "cut").

Here is what an entry might look like:

```publ
Title: My first blog entry
Date: 2018/01/04 12:34PM
Category: /blog/random

Hi, this is my first blog entry. I guess I don't have a lot to say.

.....

Well, maybe a *little* more.
```

## Headers

Headers are, more or less, a series of lines like:

```publ
Header-Name: Header-Value
Another-Header-Name: Header-Value
```

followed by a blank line. (At present, Publ actually uses Python's RFC2822 parser, so in theory you should be able
to do line continuations if that's necessary for some reason.)

You can define whatever headers you want for your
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

* **`Slug-Text`**: The human-readable part of the URL

    In some circles this is known as "SEO text."

    **Default value:** the entry title if not present, or to the entry's filename (minus extension) if there's no title.

* **`Redirect-URL`**: A URL to redirect this entry to

    This is useful if you want to remove an entry and redirect to another entry, or if
    you want an entry to be a placeholder for some external content (e.g. when the entry
    was syndicated from an external source).

    This will also override the entry's permalink.

* <a name="path-alias"></a>**`Path-Alias`**: An alternate path to this entry

    This is useful for redirecting old, non-Publ URLs to this entry. For example,
    if you're migrating from a legacy site and you have a URL like `http://example.com/blog/0012345.php`
    you can set a header like:

    ```
    Path-Alias: /blog/0012345.php
    ```

    Any number of these may be added to any given URL.

    For example, this entry has a `Path-Alias` of [`/entry-format`](/entry-format),
    and the template format page can be similarly reached at [`/template-format`](/template-format).

    **Note:** A path-alias will never override another entry at its canonical URL;
    however, it can potentially override any other kind of URL, including URLs for
    category views and non-canonical entry URLs.

* **`Path-Unalias`**: Remove an old path alias

    If you accidentally set a path-alias or want to remove it, rather than just deleting
    the `Path-Alias` header you should change it to a `Path-Unalias` (or add that header to
    another entry). This way you can ensure that the path alias will be removed from the
    index.

    ```
    Path-Unalias: /some/old/url/5-oops
    ```

* **`UUID`**: A globally-unique identifier for the entry

    While Publ doesn't use this for itself, having this sort of generated ID is
    useful for Atom feeds and the like. As such, it will be automatically generated if not present.

    It is *highly recommended* that this be unique across all entries.

* <a name="entry-type"></a>**`Entry-Type`**: An arbitrary string which you can use to define an entry type

    This exists purely so that you can differentiate entry types however you want;
    with this you can, for example, set up something similar to what WordPress and
    Tumblr call "page"-type content (to show up in a fixed navigation sidebar or the like).

    Note that this is intended for affecting the layout/structure of the site, and
    if you set more than one, only one of them will be used (and which one is undefined).
    In the future there will be a [content tagging system](https://github.com/fluffy-critter/Publ/issues/22)
    which will allow for filtering entries based on content tags.

## Entry content

After the headers, you can have entry content; if the file has a `.htm` or `.html`
extension it will just render as plain HTML, but with a `.md` extension it will
render as [Markdown](https://en.wikipedia.org/wiki/Markdown).

Publ supports [GitHub-flavored markdown](https://guides.github.com/features/mastering-markdown/),
as well as some Publ-specific tags for things like cuts, image renditions, and galleries.

Code highlighting uses the [Pygments](http://pygments.org) library, which supports
[a rather large list of syntaxes](http://pygments.org/docs/lexers/).

### Custom tags

* **`.....`**: Indicates the cut from above-the-fold to below-the-fold content (must be on a line by itself)

### <a name="image-renditions"></a>Image renditions

==**Note:** This is a [draft](http://github.com/fluffy-critter/Publ/issues/9).== Both the API and implementation are subject to change.

Publ extends the standard Markdown image tag (`![](imageFile)`) syntax with some added features for
generating display-resolution-independent renditions and [Lightbox](http://lokeshdhakar.com/projects/lightbox2/) galleries. The syntax is based on the standard Markdown for an image, which is:

```markdown
![alt text](image-path.jpg "title text")
```

(where `alt text` and `"title text"` are optional), but it adds a few features:

* Multiple images can be specified in the image list, separated by `|` characters; for example:

    ```markdown
    ![](image1.jpg "title text" | image2.jpg | image3.jpg "also title text")
    ```

* Images can be configured by adding `#(arguments)` to the filename portion or to the alt text; for example:

    ```markdown
    <!-- A single image being configured -->
    ![](image.jpg#(width=320,height=200))

    <!-- Three images configured to a width of 640, with one of them further overridden -->
    ![#(width=640)](image1.jpg | image2.jpg#(width=320) | image3.jpg)
    ```

For a full list of the configurations available, please see the manual entry on [image renditions](/image-renditions).

Image files themselves are resolved in the following order:

1. Relative to the entry file
2. Relative to the entry category in the content directory
3. Relative to the entry file's path remapped to the image directory
3. Relative to the entry category in the configured image directory
3. Absolute path in the configured image directory

So, for example, if content directory is `content/entries` and your entry is in
`content/entries/photos/my vacation/vacation.md` but indicates a category of `photos`,
and you have your image directory set to `content/images`,
an image called `DSC_12345.jpg` will be looked up in the following order:

1. `content/entries/photos/my vacation/DSC_12345.jpg`
2. `content/entries/photos/DSC_12345.jpg`
3. `content/images/photos/my vacation/DSC_12345.jpg`
3. `content/images/photos/DSC_12345.jpg`
4. `content/images/DSC_12345.jpg`

Relative paths will also be interpreted; if the filename is `../IMG_4847.jpg` the
search order will be:

1. `content/entries/photos/IMG_4847.jpg`
2. `content/entries/IMG_4847.jpg`
3. `content/images/photos/IMG_4847.jpg`
3. `content/images/IMG_4847.jpg`
4. `content/images/IMG_4847.jpg` (path sanitization prevents you from accidentally escaping each directory)

This approach allows for greater flexibility in how you manage your images; the simple
case is that the files simply live in the same directory as the entry file, and in more complex cases
things work in a hopefully-intuitive manner.

Of course, external absolute URLs (e.g. `http://example.com/image.jpg`) are still allowed, although they are
more limited in what you can do with them (for example, scaling will be done client-side and cropping
options will not work). Also, keep in mind that URLs that are not under your control may change without notice.
