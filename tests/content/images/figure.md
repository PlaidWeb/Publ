Title: Figures
Date: 2020-07-27 12:52:06-07:00
Entry-ID: 1028
UUID: 936c16b2-e4e0-56bf-923a-6dd8c6dde945

Test of `<figure>` image sets

.....

Figure=`True`:

![{figure=True}](rawr.jpg)

Caption, no explicit figure class:

![{caption='A rawr'}](rawr.jpg)

Figure class, no caption:

![{figure='rawr'}](rawr.jpg)

Caption contains markdown:

![{caption='a *rawr*[^fn]\n\n[^fn]: rawr'}](rawr.jpg)

Multiple paragraphs in caption:

![{caption='a rawr\n\nit says rawr'}](rawr.jpg)
