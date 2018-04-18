Title: Image renditions
Path-Alias: /image-renditions
Date: 2018-04-05 02:12:57-07:00
Entry-ID: 335
UUID: 8d3fa7ba-db5e-4661-bfd8-e3ee25684790

How to configure images and galleries for display

.....


==**Note:** This is a [very rough draft and is not yet implemented](https://github.com/fluffy-critter/Publ/issues/9).==

## Image rendition support

### In entries

See the [entry format article](/entry-format#image-renditions)

### In templates

Pass these in as parameters to `entry.body` and/or `entry.more`.

TODO: templates may also get an `image()` function that allows image renditions to be part of the template itself (not just entries); this will likely allow rendering out both the raw URL and an `<img src>` tag as appropriate.

## Configuration values

### Layout

* **`title`**: The title text (what pops up when you hover over it, and what Lightbox shows underneath the image)
* **`alt`**: The alternate text that is presented to text-only browsers and screen readers
* **`link`**: Put a hyperlink on the image pointing to the given URL

### Inline image sizing

* **`scale`**: What factor to scale the source image down by (e.g. 3 = the display size should be 33%)
* **`scale_min_width`**: The minimum width to target based on scaling
* **`scale_min_height`**: The minimum height to target based on scaling
* **`width`**: The maximum width to target
* **`height`**: The maximum height to target
* **`force_width`**: A value to force the width to (intended for templates)
* **`force_height`**: A value to force the height to (intended for templates)
* **`resize`**: If both `width` and `height` are specified, how to fit the image into the rectangle if the aspect ratio doesn't match
    * `fit`: Fit the image into the space (default)
    * `fill`: Fill the space with the image, cropping off the sides
    * `stretch`: Distort the image to fit
* **`fill_crop_x`**: If `resize="fill"`, where to take the cropping (0=left, 1=right); default=0.5
* **`fill_crop_y`**: If `resize="fill"`, where to take the cropping (0=top, 1=bottom); default=0.5

==**Note:** Images will never be scaled to larger than their native resolution==

### File format options

* **`format`**: Select the format to display the image as (defaults to the original format)
* **`background`**: The background color to use when converting transparent images (such as .png) to non-transparent formats (such as .jpg)
* **`quality`**: The JPEG quality level to use for all renditions
* **`quality_ldpi`**: The JPEG quality level to use for low-DPI renditions
* **`quality_hdpi`**: The JPEG quality level to use for high-DPI renditions

### Image set options

These options drive the behavior of image sets for use with [lightbox.js](http://www.lokeshdhakar.com/projects/lightbox2/).

* **`disable_lightbox`**: Set this in the template to disable lightbox (for example, for feeds)
* **`lightbox_id`**: An identifier for the Lightbox image set
    * **Note:** If this is not set, Lightbox will not be enabled, and popup renditions will not be generated
* **`limit`**: How many images to allow in the image set (useful for feeds)
* **`fullsize_width`**: The maximum width for the popup image
* **`fullsize_height`**: The maximum height for the popup image
* **`fullsize_quality`**: The JPEG quality level to use for the popup image
* **`fullsize_format`**: What format the popup image should be in (defaults to the original format)
* **`fullsize_background`**: The background color to use when converting transparent images (such as .png) to non-transparent formats (such as .jpg)
* **`container_class`**: If set, wraps the gallery in a `<div>` with the specified `class` attribute.

## Useful template examples

### A webcomic

`index.html` and `entry.html`:

This will treat source images as being 3x screen resolution, make images scale to no narrower than 480 pixels and to no wider than 960 pixels,
force them to be a JPEG (with transparency turning white), and with 35% JPEG quality for the high-DPI rendition

```jinja
{{ entry.body(
    scale=3,
    scale_min_width=480
    width=960,
    format="jpg",
    background="white",
    quality_hdpi=35)
}}
```

`feed.xml`:

This will resize the image to no more than 400 pixels wide or tall and crop the thumbnail to the top or left
of the image (making for a useful non-punchline-destroying excerpt).

```jinja
{{ entry.body(link=entry.link(
    absolute=True,
    force_width=400,
    force_height=400,
    resize="fill",
    fill_crop_x=0,
    fill_crop_y=0,
    force_size=True)
}}
```

In the above example, if you have a comic that is provided at screen resolution to begin with (such as guest art) you can override the default scaling with e.g.:

```markdown
![](guest-comic.png{scale=1} "Amazing guest comic!")
```

Or if there's one you want to force to a specific size:

```markdown
![](special-comic.jpg{scale=1,width=960,height=480})
```

### A photo gallery

`index.html`

This will show just the first image in the gallery, and then link the user to the full
gallery page.

```jinja
{{ entry.body(
    width=640,
    height=640,
    link=entry.link,
    limit=1,
    disable_lightbox=True)
    }}
```

`entry.html`

This will show the full gallery, with a reasonable default gallery ID, and the full images at 4K resolution.
The thumbnails will be wrapped in a `<div class="gallery_thumbs">`.

```jinja
{{ entry.body(
    width=640,
    height=640,
    lightbox_id="gallery-"+entry.id
    container_class="gallery_thumbs")
}}

`feed.xml`

This will show tiny thumbnails of the first three images of the gallery and will link to the full gallery page.

```jinja
{{ entry.body(
    max_width=300,
    max_height=300,
    limit=3,
    link=entry.link,
    force_size=True)
}}
