Title: Image renditions
Path-Alias: /image-renditions
Date: 2018-04-05 02:12:57-07:00
Entry-ID: 335
UUID: 8d3fa7ba-db5e-4661-bfd8-e3ee25684790

How to configure images and galleries for display

.....

## Important note

This is a [very rough draft and is not yet implemented](https://github.com/fluffy-critter/Publ/issues/9).

## Image rendition support

### In entries

See the [entry format article](/entry-format#image-renditions)

### In templates

Pass this in as a parameter to the `entry.body` and `entry.more` template thing.

For example, on a comic's `feed` template it might look like this:

```jinja
{% for entry in view.entries %}
{{entry.body(link=entry.link(absolute=True),maxWidth=300,force_size=True)}}
{% endfor %}
```

while in its `index` or `entry` template it might be:

```jinja
{{entry.body(maxWidth=960,minWidth=480)}}
```

TODO: templates may also get an `image()` function that allows image renditions to be part of the template itself (not just entries); this will likely allow rendering out both the raw URL and an `<img src>` tag as appropriate.

## Configuration values

### Applied to images

* **`title`**: The title text (what pops up when you hover over it, and what Lightbox shows underneath the image)
* **`alt`**: The alternate text that is presented to text-only browsers and screen readers
* **`minWidth`**: The minimum width the image will be scaled to
* **`maxWidth`**: The maximum width the image will be scaled to
* **`width`**: An exact width to try to target
* **`minHeight`**: The minimum height the image will be scaled to
* **`maxHeight`**: The maximum height the image will be scaled to
* **`height`**: An exact height to try to target
* **`format`**: Select the format to display the image as (defaults to the original format)
* **`background`**: The background color to use when converting transparent images (such as .png) to non-transparent formats (such as .jpg)
* **`quality`**: The JPEG quality level to use for all renditions
* **`qualityLoDPI`**: The JPEG quality level to use for low-DPI renditions
* **`qualityHiDPI`**: The JPEG quality level to use for high-DPI renditions
* **`link`**: Put a hyperlink on the image pointing to this URL (single images only)
* **`gallery`**: Which Lightbox gallery to put it in
* **`force_size`**: If `True`, don't allow the Markdown processor to override the size settings

### Applied to galleries

* **`popupWidth`**: The maximum width for the popup image
* **`popupHeight`**: The maximum height for the popup image
* **`popupQuality`**: The JPEG quality level to use for the popup image
* **`popupFormat`**: What format the popup image should be in (defaults to the original format)
* **`popupBackground`**: The background color to use when converting transparent images (such as .png) to non-transparent formats (such as .jpg)

