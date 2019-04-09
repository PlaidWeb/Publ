Title: Image size clamping
Date: 2019-01-02 20:52:52-08:00
Entry-ID: 1130
UUID: 9d91d365-f7f5-5951-bff8-1f2090ac191d

Tests for [commit `d643758`](https://github.com/PlaidWeb/Publ/commit/d643758d211e71ec06593a27fbdfb5455b1c9d40)

.....

### Local images

|  w   |  h   |  mw  |  mh  |     |
|------|------|------|------|------
| None | None | None | None | ![](rawr.jpg{width=None,height=None,max_width=None,max_height=None}) |
| None | None | None | 5 | ![](rawr.jpg{width=None,height=None,max_width=None,max_height=5}) |
| None | None | 10 | None | ![](rawr.jpg{width=None,height=None,max_width=10,max_height=None}) |
| None | None | 10 | 5 | ![](rawr.jpg{width=None,height=None,max_width=10,max_height=5}) |
| None | 25 | None | None | ![](rawr.jpg{width=None,height=25,max_width=None,max_height=None}) |
| None | 25 | None | 5 | ![](rawr.jpg{width=None,height=25,max_width=None,max_height=5}) |
| None | 25 | 10 | None | ![](rawr.jpg{width=None,height=25,max_width=10,max_height=None}) |
| None | 25 | 10 | 5 | ![](rawr.jpg{width=None,height=25,max_width=10,max_height=5}) |
| 17 | None | None | None | ![](rawr.jpg{width=17,height=None,max_width=None,max_height=None}) |
| 17 | None | None | 5 | ![](rawr.jpg{width=17,height=None,max_width=None,max_height=5}) |
| 17 | None | 10 | None | ![](rawr.jpg{width=17,height=None,max_width=10,max_height=None}) |
| 17 | None | 10 | 5 | ![](rawr.jpg{width=17,height=None,max_width=10,max_height=5}) |
| 17 | 25 | None | None | ![](rawr.jpg{width=17,height=25,max_width=None,max_height=None}) |
| 17 | 25 | None | 5 | ![](rawr.jpg{width=17,height=25,max_width=None,max_height=5}) |
| 17 | 25 | 10 | None | ![](rawr.jpg{width=17,height=25,max_width=10,max_height=None}) |
| 17 | 25 | 10 | 5 | ![](rawr.jpg{width=17,height=25,max_width=10,max_height=5}) |

### Static images

Status: This test is known to fail in Publ v0.3.13 and earlier, but will be fixed in v0.3.14.

|  w   |  h   |  mw  |  mh  |     |
|------|------|------|------|------
| None | None | None | None | ![](@images/IMG_0377.jpg{width=None,height=None,max_width=None,max_height=None}) |
| None | None | None | 5 | ![](@images/IMG_0377.jpg{width=None,height=None,max_width=None,max_height=5}) |
| None | None | 10 | None | ![](@images/IMG_0377.jpg{width=None,height=None,max_width=10,max_height=None}) |
| None | None | 10 | 5 | ![](@images/IMG_0377.jpg{width=None,height=None,max_width=10,max_height=5}) |
| None | 25 | None | None | ![](@images/IMG_0377.jpg{width=None,height=25,max_width=None,max_height=None}) |
| None | 25 | None | 5 | ![](@images/IMG_0377.jpg{width=None,height=25,max_width=None,max_height=5}) |
| None | 25 | 10 | None | ![](@images/IMG_0377.jpg{width=None,height=25,max_width=10,max_height=None}) |
| None | 25 | 10 | 5 | ![](@images/IMG_0377.jpg{width=None,height=25,max_width=10,max_height=5}) |
| 17 | None | None | None | ![](@images/IMG_0377.jpg{width=17,height=None,max_width=None,max_height=None}) |
| 17 | None | None | 5 | ![](@images/IMG_0377.jpg{width=17,height=None,max_width=None,max_height=5}) |
| 17 | None | 10 | None | ![](@images/IMG_0377.jpg{width=17,height=None,max_width=10,max_height=None}) |
| 17 | None | 10 | 5 | ![](@images/IMG_0377.jpg{width=17,height=None,max_width=10,max_height=5}) |
| 17 | 25 | None | None | ![](@images/IMG_0377.jpg{width=17,height=25,max_width=None,max_height=None}) |
| 17 | 25 | None | 5 | ![](@images/IMG_0377.jpg{width=17,height=25,max_width=None,max_height=5}) |
| 17 | 25 | 10 | None | ![](@images/IMG_0377.jpg{width=17,height=25,max_width=10,max_height=None}) |
| 17 | 25 | 10 | 5 | ![](@images/IMG_0377.jpg{width=17,height=25,max_width=10,max_height=5}) |

