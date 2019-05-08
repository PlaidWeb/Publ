Title: Mixed-mode link rewriting
Date: 2019-05-07 19:33:03-07:00
Entry-ID: 315
UUID: c6bf2121-a5fe-5813-ac21-e2ccb53fc0d8

This is a Markdown entry, but an <a href="assets.md">HTML link</a> should work the same way as a [Markdown link](assets.md).

.....

So should an HTML image:

<a href="images/notsmiley.png"><img src="images/notsmiley.png" title="This is a local image!" width=240></a>
<a href="images/boxes.svg"><img src="images/boxes.svg" title="This is a file asset!" width=240></a>

and here's a Markdown link containing an HTML image:

[<img src="images/rawr.jpg" width=160>](images/rawr.jpg)

and an HTML link containing a Markdown image:

<a href="images/rawr.jpg">![](images/rawr.jpg{width=160})</a>

and a file attachment via `<audio>`:

<audio src="boop.mp3" controls>

Also, a missing image should still get the `data-publ` debug attribute:

<img src="MISSING_FILE.png">
