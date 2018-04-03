Title: Template format
Path-Alias: /template-format
Date: 2018-04-02 18:03:58-07:00
Entry-ID: 324
UUID: cbb977df-7902-4621-af9b-36ab44401748

Publ templates use the [Jinja2](http://jinja.pocoo.org) templating system; please
see its references for the general syntax of template files.

There are three kinds of page in Publ: entry, category, and error.

## Template mapping

TODO: explain how templates are chosen in plain English

Expected templates:

* **`index`**: The default view for a category
* **`feed`**: The Atom feed for a category
* **`entry`**: The view for a single entry
* **`error`**: What to render if an error happens
    * If present, you can also use templates named for the actual error code (404, 403, etc.)

### All pages

All template types get the default Flask objects; there is more information about
these on the [Flask templating reference](http://flask.pocoo.org/docs/0.12/templating/).

Of note, the `url_for` method is available. You will probably only want to use
the `static` endpoint (for serving up static files such as stylesheets), but
you also have access to the `entry` and `category` endpoints if you need them for
some reason. (However, you will usually just be using the appropriate methods
on the objects providced to the template.)

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

    * (TODO: date, pagination, sorting, tags, etc.)



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

    (TODO: actually figure out what the arguments will be; this will be stuff
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

    (TODO: This can take arguments for getting different kinds of links; eventually
    this should be implemented and documented.)

    **Note:** If this entry is a redirection, this link refers to the redirect
    target.

* **`last_modified`**: A last-modified time for this entry (useful for feeds)

Functionality to come:

* Previous/next entry within the same category
* Previous/next entry within a specific category

### <a name="category-object"></a>Category object

The `category` object provides the following:

* **`path`**: The full path to the category

* **`basename`**: Just the last part of the category name

* **`subcats`**: The direct subcategories of this category

* **`subcats_recursive`**: All subcategories of this category, including recursive

* **`parent`**: The parent category, if any

Example template code for printing out an entire directory structure (flattened):

    <ul>
    {% for subcat in category.subcats(recurse=True) %}
    <li>subcat.path</li>
    {% endfor %}
    </ul>

Example template code for printing out the directory structure in a nice recursive manner:

    <ul>
    {%- for subcat in category.subcats recursive %}
        <li>{{ subcat.basename }}
        {%- if subcat.subcats -%}
        <ul>{{ loop(subcat.subcats)}}</ul>
        {%- endif %}</li>
    {%- endfor %}
    </ul>


### <a name="view-object"></a>View object

The `view` object has the following things on it:

* **`entries`**: A list of all of the entries that are visible in this view

* **`where(...)`**: Create another view based on this view

    This takes the same arguments as [`get_view()`](#fn-get-view); note that
    if you specify a category this will override the current view's category.

* **`last_modified`**: A last-modified time for this view (useful for feeds)
