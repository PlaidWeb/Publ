Title: Attribute renditions
Date: 2019-11-25 21:06:42-08:00
Entry-ID: 2271
UUID: 7724c5cb-95df-5a2a-941f-afa53a1588dd

.....

<img src="Landscape_1.jpg{128,128}">

<a href="Landscape_2.jpg{640,640}"><img
    id="ondemand"
    $data-ondemand="Landscape_3.jpg{192,192}"
    $data-ondemand-2x="Landscape_5.jpg{640,640}"
    data-dontinterpret="rawr.jpg"></a>

<script>
window.addEventListener('load', function() {
    var img = document.getElementById('ondemand');
    img.src = img.getAttribute('data-ondemand');
    img.srcset = img.getAttribute('data-ondemand') + ' 1x, ' + img.getAttribute('data-ondemand-2x') + ' 2x';
});
</script>
