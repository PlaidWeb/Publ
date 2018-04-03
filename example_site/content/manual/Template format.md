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

### All pages

All template types get the default Flask objects; there is more information about
these on the [Flask templating reference](http://flask.pocoo.org/docs/0.12/templating/).

Of note, the `url_for` method is available. You will probably only want to use
the `static` endpoint (for serving up static files such as stylesheets), but
you also have access to the `entry` and `category` endpoints if you need them for
some reason. (However, you will usually just be using the appropriate methods
on the objects providced to the template.)

There are also the following custom functions available:

* <a name="fn-get-view"></a>**`get_view`**: Requests a view of entries; it takes the following arguments:

    * **`category`**: The top-level category to consider

        **Note:** If this is left unspecified, it will always include entries from the entire site

    * **`recurse`**: Whether to include subcategories

        * `True`: Include subcategories
        * `False`: Do not include subcategories (default)

    * (TODO: date, pagination, sorting, tags, etc.)



### Entry pages

Specific entries are always rendered with its category's `entry` template.
The template gets the following parameters to it:

* **`entry`**: Information about the [entry](#entry-object)
* **`category`**: Information about the [category](#category-object)

### Category pages

Categories are rendered with whatever template is specified, defaulting to `index`
if none was specified. The template gets the following parameters:

* **`category`**: Information about the [category](#category-object)
* **`view`**: Information about the [view](#view object)

### Error pages

Error templates do not receive any additional parameters beyond what all templates
get.

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

### <a name="category-object"></a>Category object

TODO

### <a name="view-object"></a>View object

The `view` object has the following things on it:

* **`entries`**: A list of all of the entries that are visible in this view

* **`where(...)`**: Create another view based on this view

    This takes the same arguments as [`get_view()`](#fn-get-view); note that
    if you specify a category this will override the current view's category.
