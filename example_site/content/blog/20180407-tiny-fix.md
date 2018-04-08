Title: Just one tiny fix today
Date: 2018-04-07 23:32:57-07:00
Entry-ID: 344
UUID: a210f0fa-6e75-4b6f-9603-f85bf1f52b03

I am trying to make my weekends actual weekends, so the only thing I did
on Publ today was to refactor the way that properties with optional arguments
work. Previously I was using a hack that only worked for string-type things
(such as links), but now I'm using a better hack that works for every sort of
object you might throw at it.

.....

So the upshot is that now `entry.previous` and `entry.next` take arguments
directly; for example:

```jinja
{% set prev_on_site = entry.previous(category='',recurse=True) %}
```

makes the `prev_on_site` variable refer to the previous entry anywhere on
the site across all categories. There is no longer any need for separate `next` and `next_in` properties, as a result, so this simplifies the API a lot, which
makes me happy.

Anyway, here is my current priority list:

1. View pagination
2. Image renditions
3. Start migrating [beesbuzz.biz](http://beesbuzz.biz/) to Publ

These also happen to be in increasing order of complexity. How convenient.

For my migration plan I think I'll start with just the [photography section](http://beesbuzz.biz/art/photography) since that touches all of the key points on
image renditions, and then next I'll move on to the [comics](http://beesbuzz.biz/d/) since that is where paginations and entry types become important.

The blog I will probably save for much, much later, if ever, because holy cow there's a lot of content there I don't care about, and a huge amount of fiddly things to worry about. (Plus, I never got around to migrating the comments over to Disqus, and I have a bunch of stuff there that I'd rather still be behind a friends-only ACL. I'll *probably* just omit those entries for now, if it's all the same.)

Anyway. This project is coming along much more quickly than I expected it to! And I've learned a lot about Python while doing it. Neat.

I've also learned a bunch about Dreamhost and Passenger as well, although I'd really like to understand why I have to restart my app instance to make rendered
templates re-render... There seems to be some sort of obnoxious caching behavior, or something. This I will definitely need to address.
