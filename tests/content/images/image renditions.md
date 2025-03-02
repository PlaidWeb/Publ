Title: Test of image renditions
Date: 2018-04-05 02:17:49-07:00
Entry-ID: 336
UUID: a28a68eb-c668-4fb8-9d3a-6cbcc3920772
Last-Modified: 2020-01-04 09:59:41+00:00

Image rendition tests

.....

## External images

External image with width set

![](//placecats.com/800/600{250} "so smol")

`![](//placecats.com/800/600{250} "so smol")`

External image with height set

![](//placecats.com/800/600{height=250} "less smol")

`![](//placecats.com/800/600{height=250} "less smol")`

External image with width and height set, with different scaling modes:

![{320,320,div_class="gallery",gallery_id="sizing"}](
//placecats.com/960/480 "fit"
| //placecats.com/960/480{resize="fill"} "fill"
| //placecats.com/960/480{resize="stretch"} "stretch")

```markdown

![{320,320,div_class="gallery",gallery_id="sizing"}](
//placecats.com/960/480 "fit"
| //placecats.com/960/480{resize="fill"} "fill"
| //placecats.com/960/480{resize="stretch"} "stretch")
```

Image using static path

![{640,link='@images/IMG_0377.jpg'}](@images/IMG_0377.jpg)

`![{640,link='@images/IMG_0377.jpg'}](@images/IMG_0377.jpg)`


Force absolute URLs

![{640,320,absolute=True}](//placecats.com/800/600 | @images/IMG_0377.jpg | critter.webp{999,format='png'})

`![{640,320,absolute=True}](//placecats.com/800/600 | @images/IMG_0377.jpg | critter.webp{999,format='png'})`


## Local images

![alt text](rawr.jpg "test single image")

`![alt text](rawr.jpg "test single image")`

![alt text](
rawr.jpg{width=240} "test lightbox" |
rawr.jpg{width=120} |
rawr.jpg "image 3"
)

```markdown

![alt text](
rawr.jpg{width=240} "test lightbox" |
rawr.jpg{width=120} |
rawr.jpg "image 3"
)
```

![alt text](rawr.jpg "test single image")

`![alt text](rawr.jpg "test single image")`

![alt text](rawr.jpg{120,crop=(0,0,240,352)} "test crop (left half of rawr.jpg, scaled down)")

```markdown

![alt text](rawr.jpg{120,crop=(0,0,240,352)} "test crop (left half of rawr.jpg, scaled down)")
```

![](rawr.jpg{gallery_id='crops',crop=(107,72,89,82)} "just rawr's eye")

```markdown

![](rawr.jpg{gallery_id='crops',crop=(107,72,89,82)} "just rawr's eye")
```

![](croptest.png{gallery_id='crops',crop=(462,389,183,133),fullsize_crop=(119,142,343,247)}
    "different crops for thumbnail as fullsize")

```markdown

![](croptest.png{gallery_id='crops',crop=(462,389,183,133),fullsize_crop=(119,142,343,247)}
    "different crops for thumbnail as fullsize")
```

![{100,100}](
  croptest.png{crop='119,142,343,247',resize='fit'} "fit crop"
| croptest.png{crop='119,142,343,247',resize='fill'} "fill crop")

```markdown

![{100,100}](
  croptest.png{crop='119,142,343,247',resize='fit'} "fit crop"
| croptest.png{crop='119,142,343,247',resize='fill'} "fill crop")
```



Inline image with a gallery class: ![{div_class="images"}](rawr.jpg{32,32}) should still be a block element

Inline image with no gallery class: ![{div_class=None}](rawr.jpg{32,32}) should be inline

Paragraph-level image set without a gallery class:

![{div_class=None}](rawr.jpg
| rawr.jpg
| rawr.jpg)

should still be in a paragraph

## Mixed-content gallery

![such gallery{255,gallery_id="rawry"}](rawr.jpg
| rawr.jpg{fullscreen_width=50} "Rawr!"
| rawr.jpg{100}
| //placecats.com/1280/720)

```markdown

![such gallery{255,gallery_id="rawry"}](rawr.jpg | rawr.jpg{fullscreen_width=50} "Rawr!" | rawr.jpg{100}
| //placecats.com/800/600)
```

## PNG transparency

Base image:

![](notsmiley.png) `![](notsmiley.png)`

converted to jpeg, no background:

![](notsmiley.png{format="jpg"}) `![](notsmiley.png{format="jpg"})`

converted to jpeg, black background:

![](notsmiley.png{format="jpg",background="black"}) `![](notsmiley.png{format="jpg",background="black"})`


converted to jpeg, red background using a tuple:

![](notsmiley.png{format="jpg",background=(255,0,0)}) `![](notsmiley.png{format="jpg",background=(255,0,0)})`

converted to jpeg, white background using hex code:

![](notsmiley.png{format="jpg",background='#ccc'}) `![](notsmiley.png{format="jpg",background='#ccc'})`


converted to jpeg, cyan background, multiple qualities on the spectrum:

![{256,background='cyan',format='jpg'}](
notsmiley.png{quality=1} "quality 1"
| notsmiley.png{quality=50} "quality 50"
| notsmiley.png{quality=99} "quality 99"
| notsmiley.png "quality default"
)

```markdown

![{256,background='cyan',format='jpg'}](
notsmiley.png{quality=1} "quality 1"
| notsmiley.png{quality=50} "quality 50"
| notsmiley.png{quality=99} "quality 99"
| notsmiley.png "quality default"
)
```

## Quantization

![{256,256}](Landscape_4.jpg "default"
| Landscape_4.jpg{format='png'} "png24"
| Landscape_4.jpg{format='png',quantize=0} "png8 0"
| Landscape_4.jpg{format='png',quantize=128} "png8 128"
| Landscape_4.jpg{format='png',quantize=32} "png8 32"
| Landscape_4.jpg{format='png',quantize=4} "png8 4"
| Landscape_4.jpg{format='png',quantize=2} "png8 2"
| Landscape_4.jpg{format='png',quantize=256} "png8 256"
| Landscape_4.jpg{format='gif'} "gif8"
| Landscape_4.jpg{quantize=16} "jpeg 16"
)

```markdown

![{256,256}](Landscape_4.jpg{format='png'} "png24"
| Landscape_4.jpg{format='png',quantize=0} "png8 0"
| Landscape_4.jpg{format='png',quantize=128} "png8 128"
| Landscape_4.jpg{format='png',quantize=32} "png8 32"
| Landscape_4.jpg{format='png',quantize=4} "png8 4"
| Landscape_4.jpg{format='png',quantize=2} "png8 2"
| Landscape_4.jpg{format='gif'} "gif8"
| Landscape_4.jpg{quantize=16} "jpeg 16"
)
```

## Scale algorithms

![{128,128,format='png'}](Landscape_1.jpg "default"
| Landscape_1.jpg{scale_filter='nearest'} "nearest"
| Landscape_1.jpg{scale_filter='box'} "box"
| Landscape_1.jpg{scale_filter='bilinear'} "bilinear"
| Landscape_1.jpg{scale_filter='hamming'} "hamming"
| Landscape_1.jpg{scale_filter='bicubic'} "bicubic"
| Landscape_1.jpg{scale_filter='lanczos'} "lanczos"
| Landscape_1.jpg{scale_filter='xyzzy'} "xyzzy"
)

```markdown

![{128,128,format='png'}](Landscape_1.jpg "default"
| Landscape_1.jpg{scale_filter='nearest'} "nearest"
| Landscape_1.jpg{scale_filter='box'} "box"
| Landscape_1.jpg{scale_filter='bilinear'} "bilinear"
| Landscape_1.jpg{scale_filter='hamming'} "hamming"
| Landscape_1.jpg{scale_filter='bicubic'} "bicubic"
| Landscape_1.jpg{scale_filter='lanczos'} "lanczos"
| Landscape_1.jpg{scale_filter='xyzzy'} "xyzzy"
)
```

## Broken/parse failures

* `![broken image](missingfile.jpg)`

    ![broken image](missingfile.jpg)


* `![broken spec](foo{123[]})`

    ![broken spec](foo{123[]})

* `![broken spec](poiu{100} foo{200})`

    ![broken spec](poiu{100} foo{200})

* `![broken imageset](rawr.jpg rawr.jpg)`

    ![broken imageset](rawr.jpg rawr.jpg)

* `![broken imageset](rawr.jpg "title rawr" rawr.jpg "title 2")`

    ![broken imageset](rawr.jpg "title rawr" rawr.jpg "title 2")

* `![partially broken image set](rawr.jpg "rawr!" | missingfile.jpg "missing")`

    ![partially broken image set](rawr.jpg "rawr!" | missingfile.jpg "missing")

* `![too many posargs](rawr.jpg{2,3,4})`

    ![too many posargs](rawr.jpg{2,3,4})

* `![mulitple widths](rawr.jpg{100,width=200})`

    ![mulitple widths](rawr.jpg{100,width=200})
