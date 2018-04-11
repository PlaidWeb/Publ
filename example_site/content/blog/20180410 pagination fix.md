Title: Pagination corrected
Date: 2018-04-11 00:06:06-07:00
Entry-ID: 347
UUID: 9f490386-6f95-4706-b583-c79b2409b51c

There was a silly bug with how I was generating paginated views which I noticed
as soon as I did my commit/merge last night but I figured I'd wait until today
to fix it (because the fix was obvious and I was already up way too late).
And I fixed it.

So.

There is only one feature left before I can start making a real site with this
thing: Image renditions.

This is the single most important feature (at least for the initial phase of
Publ), and in fact about 95% of the reason
why I decided to write a new CMS to handle my site content; this is the one thing
that every CMS I've seen does a poor job of handling, and which is very difficult
to hack around. (I hacked around it in Movable Type, [as I mentioned previously](325),
and it is one of the most irritating things about running my site as it is.)

.....

I've been thinking a lot about how to make this work. Misaka not allowing me to
extend the markup engine with additional tags ended up being a blessing in
disguise, as it forced me to think about better ways of doing it. The better
way that occurs to me is to add optional parameters to the standard Markdown
image tag. You can read my latest thoughts about it [over yonder](/entry-format#image-renditions).
No need to rehash what I've written in so many other places already.

Anyway. In addition to being the single most important/distinguishing feature
of Publ, it's also
probably the single most difficult to implement (I mean, there's a reason why
other CMSes just sort of punt on it, right?). I've thought about it so much
that I feel like actually writing the code is just going through the motions but
it's possible that everything is going to fall down like a house of cards when
it comes to actually writing code.

My initial plan for renditions is to go in roughly this order:

1. Support parsing the extended Markdown tag
2. Generate a base rendition that ignores all options
3. Implement `width` and `height` (and `force_width` and `force_height` which
    are basically "free"), with only `fit` and `stretch` resizing
4. Implement `scale`, `scale_min_with`, `scale_min_height`
5. `popup_width` `popup_height` `container_class` `lightbox_id`
6. `fill` resizing (including `fill_crop_x` and `fill_crop_y`)
7. `format`, `background`, and the various `quality` tags
8. ... I think that's it?

At this point, Publ will have everything I need to port all of the existing
[busybee website](http://beesbuzz.biz/) over to it (and do it better than it
was already). So then I can start on
*that* massive undertaking.