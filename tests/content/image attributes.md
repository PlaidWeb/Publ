Title: Image attributes
Date: 2018-09-21 00:38:19-07:00
Entry-ID: 516
UUID: b1042af0-6485-5580-8731-c123a9c5c530

Tests of `div_class`, `img_class`, `div_style`, `img_style`, and `style`

.....

![setting div_class and img_class{div_class="foo",img_class="bar"}](
    rawr.jpg{img_class="rawr"} "overriding img_class to rawr" |
    rawr.jpg "no override, should be bar"
)

![setting div_style, img_style, style{div_style="border:solid cyan 1px",img_style="border-color:blue",style="border-style:dotted"}](
    rawr.jpg{img_style="border-color:green"} "dotted green border" |
    rawr.jpg{style="border-style:solid"} "solid blue border" |
    rawr.jpg{img_style="border-color:green",style="border-style:solid"} "solid green border"
    )