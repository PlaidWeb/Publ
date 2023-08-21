Title: Gallery link stuff
Date: 2023-08-20 23:31:47-07:00
Entry-ID: 25
UUID: 526bd679-aa2b-5b36-aecc-485ea1de0eeb

Tests of how image links resolve

.....

<style>
a img {
    border:solid green 5px;
}
a[data-lightbox] img {
    border: solid red 5px;
}
a[href="https://example.com/"] img {
    border: solid yellow 5px;
}
</style>

![{240,240}](Landscape_1.jpg "default"
| Landscape_1.jpg{gallery_id='foo'} "gallery_id specified"
| Landscape_1.jpg{link='https://example.com/'} "link specified"
| Landscape_1.jpg{link='https://example.com/',gallery_id='bar'} "gallery_id and link specified"
| Landscape_1.jpg{link=False,gallery_id='baz'} "gallery_id specified, link suppressed"
| Landscape_1.jpg{link=True} "self-link"
| Landscape_1.jpg{link=True,gallery_id='quuz'} "self-link with gallery_id"
| Landscape_1.jpg{link=True,fullsize_width=100,fullsize_height=100} "self-link with custom size"
)
