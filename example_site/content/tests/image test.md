Title: Test of image renditions
Date: 2018-04-05 02:17:49-07:00
Entry-ID: 336
UUID: a28a68eb-c668-4fb8-9d3a-6cbcc3920772

Image rendition tests

.....

External image:

![](http://beesbuzz.biz/d/lewi/lewi-51.jpg)

External image in a link and with width set:

[![](http://beesbuzz.biz/d/lewi/lewi-52.HIDPI.jpg{250} "so smol")](http://beesbuzz.biz/d/)

Local image:

![alt text](rawr.jpg "test single image")

![alt text](
rawr.jpg{width=240} "test lightbox" |
rawr.jpg{width=120} |
rawr.jpg "image 3"
)

![alt text](rawr.jpg "test single image")

![broken image](alsdkfjaks asdlfkas fsalkfj salfsa)

![broken spec](foo{123[]})

![broken spec](poiu{100} foo{200})


![such gallery{255,gallery_id="rawry"}](rawr.jpg | rawr.jpg{fullscreen_width=50} "Rawr!" | rawr.jpg{100}
| http://beesbuzz.biz/d/lewi/lewi-52.HIDPI.jpg)