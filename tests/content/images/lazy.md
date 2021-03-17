Title: lazy image loading
entry-template: _loading
image-loading: lazy
Date: 2021-03-16 20:31:25-07:00
Entry-ID: 653
UUID: 5f3d8072-ffb7-52e3-969e-60fc5efb812c

Entry specifies images as lazy-loading

.....

Default:

![](Landscape_1.jpg)

Eager:

![](Landscape_2.jpg{image_loading='eager'})

Lazy:

![](Landscape_3.jpg{image_loading='lazy'})

Invalid:

![](Landscape_4.jpg{image_loading='invalid'})

`False`:

![](Landscape_4.jpg{image_loading=False})

`None`:

![](Landscape_4.jpg{image_loading=None})

