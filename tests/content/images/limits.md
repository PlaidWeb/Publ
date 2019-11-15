Title: Gallery with limits
Date: 2019-11-15 11:56:52-08:00
Entry-ID: 1864
UUID: 24428234-e819-5c32-9197-2d245c809971

Show only the third image on the index, full gallery in entry:

![{index_count=1,count_offset=2,index_link='1864',gallery_id='truncated'}](rawr.jpg "one" | rawr.jpg "two" | rawr.jpg "three" | rawr.jpg "four" | rawr.jpg "five")

.....

No limit:

![](rawr.jpg "one" | rawr.jpg "two" | rawr.jpg "three" | rawr.jpg "four" | rawr.jpg "five")

`count=3`

![{count=3,more_text="count={count},remain={remain}"}](rawr.jpg "one" | rawr.jpg "two" | rawr.jpg "three" | rawr.jpg "four" | rawr.jpg "five")

`count_offset=2`

![{count_offset=2,more_text="count={count},remain={remain}"}](rawr.jpg "one" | rawr.jpg "two" | rawr.jpg "three" | rawr.jpg "four" | rawr.jpg "five")

`count=3,count_offset=2`

![{count=3,count_offset=2,more_text="count={count},remain={remain}"}](rawr.jpg "one" | rawr.jpg "two" | rawr.jpg "three" | rawr.jpg "four" | rawr.jpg "five")

`link='/',count=3,count_offset=2`

![{link='/',count=3,count_offset=2,more_text="count={count},remain={remain}"}](rawr.jpg "one" | rawr.jpg "two" | rawr.jpg "three" | rawr.jpg "four" | rawr.jpg "five")

`gallery_id='test',count=2,count_offset=1`

![{gallery_id='test',count=2,count_offset=2,more_text="count={count},remain={remain}"}](rawr.jpg "one" | rawr.jpg "two" | rawr.jpg "three" | rawr.jpg "four" | rawr.jpg "five")
