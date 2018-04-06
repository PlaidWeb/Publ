Title: Better Markdown, trying to pace myself
UUID: 94513c68-87e7-42a8-8957-352a896a0a82
Date: 2018-04-06 01:15:50-07:00
Entry-ID: 338

So, I have a problem where when I really get into a project I start to work
myself to death on it. Perhaps not *literally*, but enough so that my limbic
system thinks I'm dying. Last night I had a panic attack -- my first in quite
some time -- due to me having pushed myself too hard.

Fortunately this project is getting to a point where I can slow down my
development, which is pretty necessary for my sanity and long-term survival!

.....

Anyway, here's the major points of what I did last night:

* Experimented with how I might go about supporting image renditions
* Discovered that the [Misaka](http://misaka.61924.nl) Markdown library,
    despite not allowing for custom tags, does allow you to override the behavior
    of the image tag (`![]()`), and after some testing found that its
    implementation even allows some of the more advanced syntactical fun I wanted
    for this purpose! So I switched to Misaka.
* While I was at it, I added in [Pygments](http://pygments.org), a syntax
    highlighter that is easy to support through one of Misaka's extensions.
    So now you might notice some pretty syntax highlighting on the
    [various](/entry-format) [manual](/template-format) [pages](/image-renditions).

Incidentally, I haven't found a suitable highlighter for publ entry format
(there's an `rfc2822` module but Publ doesn't follow its `Date` format),
so if someone wants to write one that'd be appreciated! Even if it's of
incredibly niche interest (pretty much only for the Publ site itself,
really). Fortunately an actual parser shouldn't be *too* hard to implement;
it only needs to know about `Key: Value` headers, transition to the body, and
`.....` cuts. Well, and I guess it'd be great if the body fell back to `markdown`
syntax.

Oh, and I also wrote out a detailed spec for how [image renditions](/image-renditions)
might work. This is, as I said [earlier](325), one of the biggest, most
important parts of this project, and I'm really hoping I got it right!

The actual image scaling aspect in particular might seem a bit counterintuitive
but it's based on the actual workflow I was using for my comics, and everything
is functionality that I have very specifically wanted and can see a lot of
use for. But there might be some use case I've missed, or something might be
redundant or better-expressed in some other way.

Also! While Misaka is generally better than Python-Markdown in pretty much
every way that matters (robustness, speed, support for fenced code, conveniently
mutable image tag parsing, ~~strikethrough~~, tables,footnotes, ==highlighting==,
...) it does have a
couple of downsides; in particular,
as I mentioned above it doesn't have a custom tag extension mechanism (at least,
not without forking the underlying C library which leads to a whole huge mess I
definitely do *not* want to touch as part of Publ).

This means that some
functionality I was hoping to add at some point is pretty much off the table.
For example, being able to support custom tags for embeds from standard sites;
I wanted to eventually make it possible to do something like (for example)
`{embed|http://soundcloud.com/plaidfluff/spookstep}` and have inference rules
automatically expand that to

<iframe width="100%" height="120" scrolling="no" frameborder="no" allow="autoplay" src="https://w.soundcloud.com/player/?url=https%3A//api.soundcloud.com/tracks/229594286&color=%23ff5500&auto_play=false&hide_related=false&show_comments=true&show_user=true&show_reposts=false&show_teaser=true&visual=true"></iframe>

or the like. But, hey, embeds work, so for now it's okay for people to
do that manually, right?

That said, the way Misaka implements the Hoedown renderer specification means
that any of its tag extensions *could* be used as a hook for some other custom
functionality. So maybe ==highlighting== could be replaced... or, heck, it's not
out of the question to simply extend the `[link](syntax)` for "please embed this" --
maybe in the future, writing code like `[@embed](http://http://music.sockpuppet.us/track/a-better-day)`
would render like

<iframe style="border: 0; width: 100%; height: 42px;" src="http://bandcamp.com/EmbeddedPlayer/album=1413796988/size=small/bgcol=ffffff/linkcol=0687f5/track=436704743/transparent=true/" seamless><a href="http://music.sockpuppet.us/album/novembeat-2017">Novembeat 2017 by Sockpuppet</a></iframe>

instead.

The more I think about this (thanks, all you
[rubber ducks](https://en.wikipedia.org/wiki/Rubber_duck_debugging) out there!]
the more I like this -- it's in keeping with the mentality of simply extending things in an
intuitive, humane way, right?

So, yeah, let me just state for the record that I am pretty sure that embeds
will be handled via `[@embed|arg1|arg2|...](link goes here)` and that this will
be a really useful extension for Publ to express.

Got comments on this proposal? Talk about it on [the open issue](https://github.com/fluffy-critter/Publ/issues/26)!

Anyway, I'm going to bed before I work myself into another panic attack. Goodnight, y'all!
