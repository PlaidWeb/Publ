Title: Template format
Path-Alias: /template-format
Date: 2018-04-02 18:03:58-07:00
Entry-ID: 324
UUID: cbb977df-7902-4621-af9b-36ab44401748

A guide to building templates for Publ

.....

Publ templates use the [Jinja2](http://jinja.pocoo.org) templating system; please
see its references for the general syntax of template files.

There are three kinds of page in Publ: entry, category, and error.

## Template mapping

TODO: explain how templates are chosen in plain English ([issue 10](https://github.com/fluffy-critter/Publ/issues/10))

Expected templates:

* **`index`**: The default view for a category
* **`feed`**: The Atom feed for a category
* **`entry`**: The view for a single entry
* **`error`**: What to render if an error happens
    * If present, you can also use templates named for the actual error code (404, 403, etc.)

### All pages

All template types get the default Flask objects; there is more information about
these on the [Flask templating reference](http://flask.pocoo.org/docs/0.12/templating/).

The following additional things are provided to the request context:

* **`arrow`**: The [Arrow](https://arrow.readthedocs.io/en/latest/) time library

* <a name="fn-get-view"></a>**`get_view`**: Requests a view of entries; it takes the following arguments:

    * **`category`**: The top-level category to consider

        **Note:** If this is left unspecified, it will always include entries from the entire site

    * **`recurse`**: Whether to include subcategories

        * `True`: Include subcategories
        * `False`: Do not include subcategories (default)

    * **`future`**: Whether to include entries from the future

        * `True`: Include future entries
        * `False`: Do not include future entries (default)

    * **`limit`**: Limit to a maximum number of entries

    * **`entry_type`**: Limit to entries with a specific [`Entry-Type`](/entry-format#entry-type) header
    * **`entry_type_not`**: Limit to entries which do NOT match a specific entry type

        These can be a single string, or it can be an array of strings. Note that
        these are case-sensitive (i.e. `"PaGe"` and `"pAgE"` are two different types).

        * `get_view(entry_type='page')` - only get entries of type "page"
        * `get_view(entry_type_not='page')` - only get entries which AREN'T of type "page"
        * `get_view(entry_type=['news','comic'])` - get entries which are of type 'news' or 'comic'
        * `get_view(entry_type_not=['news','comic'])` - get entries of all types except 'news' or 'comic'

        Mixing `entry_type` and `entry_type_not` results in undefined behavior, not that it makes
        any sense anyway.

    * ([TODO](https://github.com/fluffy-critter/Publ/issues/13): date, pagination, sorting, tags, etc.)

* **`static`**: Build a link to a static resource. The first argument is the path within the static
    resources directory; it also takes the following optional named arguments:

    * **`absolute`**: Whether to force this link to be absolute
        * `False`: Use a relative link if possible (default)
        * `True`: Use an absolute link

As a note: while `url_for()` is available, it shouldn't ever be necessary, as all
the other endpoints are accessible via higher-level wrappers (namely **`static`**, **`category`**, and **`entry`**).

### Entry pages

Specific entries are always rendered with its category's `entry` template.
The template gets the following additional objects:

* **`entry`**: Information about the [entry](#entry-object)
* **`category`**: Information about the [category](#category-object)

### Category pages

Categories are rendered with whatever template is specified, defaulting to `index`
if none was specified. The template gets the following additional objects:

* **`category`**: Information about the [category](#category-object)
* **`view`**: Information about the [view](#view object)

### Error pages

Error templates receive an `error` object to indicate which error occurred;
otherwise it only gets the default stuff. This object has the following
properties:

* **`code`**: The associated HTTP error code
* **`message`**: An explanation of what went wrong

## Object interface

### <a name="entry-object"></a>Entry object

The `entry` object has the following methods/properties:

* **`id`**: The numerical entry ID
* **`body`** and **`more`**: The text above and below the fold, respectively

    These properties can be used directly, or they can be used as functions
    which affect the content rendering. For example:

    ([TODO](https://github.com/fluffy-critter/Publ/issues/9): actually figure out what the arguments will be; this will be stuff
    like image renditions, auto-excerpts, etc.)

* All headers on the [entry file](/entry-format) are available

    These can be accessed either with `entry.header` or `entry['header']`. If
    there is a `-` character in the header name you have to use the second
    format, e.g. `entry['some-header']`.

    If there is more than one header of that name, this will only retrieve
    one of them (and which one isn't defined); if you want to get all of them
    use `entry.get_all('header')`. For example, this template fragment
    will print out all of the `Tag` headers in an unordered list, but only
    if there are any `Tag` headers:

        {% if entry.Tag %}
        <ul>
            {% for tag in entry.get_all('Tag') %}
            <li>{{ tag }}</li>
            {% endfor %}
        </ul>
        {% endif %}

* **`link`**: A link to the entry's individual page

    This can take arguments for different kinds of links; for example:

    * **`absolute`**: Whether to format this as an absolute or relative URL
        * **`False`**: Use a relative link (default)
        * **`True`**: Use an absolute link
    * **`expand`**: Whether to expand the URL to include the category and slug text
        * **`False`**: Use a condensed link
        * **`True`**: Expand the link to the full entry path (default)

    ([TODO](https://github.com/fluffy-critter/Publ/issues/15))

    **Note:** If this entry is a redirection, this link refers to the redirect
    target.

* **`permalink`**: A permanent link to the entry

    This is similar to **`link`** but subtly different; it only accepts the
    **`absolute`** and **`expand`** arguments, and it never follows a redirection.

    Whether to use an expanded link or not depends on how "permanent" you want your
    permalink to be; a condensed link will always cause a redirect to the current
    canonical URL, but an expanded link may go obsolete and still cause a redirection.
    The expanded link is generally better for SEO, however, and thus it is the default
    even if it isn't truly "permanent." (But then again, what *is* permanent, anyway?)

    Unlike **`link`** this will never follow a redirection.

* **`last_modified`**: A last-modified time for this entry (useful for feeds)

Functionality to come:

* Previous/next entry within the same category
* Previous/next entry within a specific category

### <a name="category-object"></a>Category object

The `category` object provides the following:

* **`path`**: The full path to the category

* **`basename`**: Just the last part of the category name

* **`subcats`**: The direct subcategories of this category

* **`subcats_recursive`**: All subcategories below this category

* **`parent`**: The parent category, if any

* **`link`**: The link to the category; callable as a function which takes the
    following arguments:

    * **`template`**: Which template to use when rendering the category
    * **`absolute`**: Whether to format this as an absolute or relative URL
        * **`False`**: Use a relative link (default)
        * **`True`**: Use an absolute link

Example template code for printing out an entire directory structure (flattened):

    <ul>
    {% for subcat in category.subcats(recurse=True) %}
    <li>subcat.path</li>
    {% endfor %}
    </ul>

Example template code for printing out the directory structure in a nice recursive manner:

    <ul>
    {% for subcat in category.subcats recursive %}
        <li>{{ subcat.basename }}
        {% if subcat.subcats %}
        <ul>{{ loop(subcat.subcats)}}</ul>
        {% endif %}</li>
    {% endfor %}
    </ul>


### <a name="view-object"></a>View object

The `view` object has the following things on it:

* **`entries`**: A list of all of the entries that are visible in this view

* **`last_modified`**: A last-modified time for this view (useful for feeds)

* **`spec`**: The view's specification (category, limits, date range, etc.)

It also takes arguments to further refine the view, using the same arguments
as [`get_view()`](#fn-get-view); for example:

    {% for entry in view(limit=10) %}{{entry.title}}{% endfor %}

Note that if you specify a category this will override the current view's category.

