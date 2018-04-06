Title: The first weblog entry about (and using) Publ!
Date: 2018-04-03 09:00:00-07:00
Entry-ID: 325
UUID: e0f0ac51-9ef6-4a52-a87a-9847f60600bb

This is the first blog entry on Publ! It's pretty exciting to finally have this
posted.

Publ is a system I've been thinking about building for quite a long time, and over
the last few years it's been occupying an especially high-priority slot in the back of my mind.
Let's talk
a bit about the history and why I decided to build Yet Another CMS.

.....

## History

### Pre-Cambrian era

Back in the year 2000 (when blogs were still called "web logs" and dinosaurs roamed the earth)
I was pretty active on
kuro5hin.org (now defunct). It was a pretty interesting community platform, which
started out as a news site but eventually turned into a journaling site. It had
a lot of shared experience and content thereof, and a nice community of technology enthusiasts.

Then in late 2001 some people flew some planes into some buildings, and suddenly the tone of the site changed.

It was now mostly about politics. And with politics came a lot of... let's say *differing* opinions.
Which is fine, but some of the debates got pretty heated, and this ended up attracting a bunch of trolls,
who enjoyed picking at the various scabs of the community.

Throughout the early history of the site I was
open about my gender despite not being particularly public about it in meatspace.
Due to this I had a particularly gigantic target on my back.

I got doxed.

One of the basic tenets of kuro5hin was that the community should be self-moderating, but
the community was now overrun by bad actors. Another basic tenet wqs that nobody should be
allowed to delete their own stuff, as it was a "community site" and nobody wanted a "memory
hole," and meanwhile the only person with the ability to delete anything was the site owner,
who believed that trying to remove information from the Internet is like "trying to extract
urine from a pool," so he refused to do anything about the information I wanted taken down
since he felt it wouldn't make any difference anyway.

(One particularly *fun* thing was one of the trolls registered an account under my
then-legal name, and started reposting all of my content under that account. *Fun times.*)

In January 2003 I decided that the only thing I could really do was leave the site and run my
own blog where I had full control over my content, with the ability to ban trolls and delete
any content I no longer wanted to actively present to the Internet.

### Movable Type times

Movable Type was a pretty good system for a basic blog. Heck, it's still pretty good
for a lot of things. Especially if all of your content is uniform.

I wanted to have more and more stuff managed by a high-level CMS on my site, which
I hacked together with multiple sites on a single domain, with some shoddy glue to
keep it all together. In 2004 I integrated the phpBB forum engine with Movable Type
to use it as a comment system.

In 2004 I worked for a game company and wanted to keep blogging but didn't want
everything to be world-readable, so I hacked access control into my blog templates
using the phpBB user system to drive it. This worked *okay* but it wasn't great.

In 2005 I decided to start posting serial comics again; I had been posting occasional
journal comics to my blog (which worked *okay* but wasn't great), and prior to that
I'd made purpose-specific CMSes for my serial comics but maintaining that was a huge
chore and I never got things like RSS feeds working with it. So I hacked together
some comic-publishing templates for Movable Type and set it up as another sub-site.

Also around this time I decided to start using Movable Type to manage the rest of my
site content, including photos, music, and a bunch of other unstructured things. This
involved even more hacks with CSS and PHP to make things look kinda-sorta integrated
even though they weren't.

I had so many separate feeds, so at one point I made a "feed glommer" that was yet
another PHP hack that would aggregate all my existing feeds together.

I played with Wordpress for some sites but it was fragile and easily-hacked, so I decided to stay away from that.

I played with Jekyll and Octopress for another site but maintaining it was a gigantic pain in the butt,
and I didn't want to have to learn Ruby and its various invocations just to post an entry.

By this point my web presence was a sprawling mess and I didn't really like
maintaining any of my stuff. And everyone was moving to Facebook and Tumblr
anyway, so for new sites I just started using those things as appropriate.

Also, high-DPI displays happened, and I decided I wanted to publish my comics in a high-DPI-compatible
manner. But no CMSes out there supported this, so, of course, I started hacking it into Movable Type.

You really don't want to see all of the weird moving parts that go behind serving up a single comic.

### Many walled gardens

So, now I had a whole bunch of mess to deal with. I basically stopped blogging
on my own site (who the heck reads personal blogs anymore, anyway?). I still posted
comics to my MT-based site, and then used IFTTT to syndicate that content over
to Facebook and Tumblr. I started to only post my music on Soundcloud (with IFTTT to
republish it on Facebook and Tumblr).

I wanted to republish my external stuff over to my site but Movable Type doesn't provide
an easy way to slurp in external content from feeds; neither does Tumblr.

So many uses of walled-garden services that I don't control.

But managing all this stuff was a nightmare, and I was getting really sick of corporations
being in charge of my web-based publishing, and then Twitter, Facebook, and Tumblr all
started to have problems with toxic communities and a house of cards falling down around
privacy and data ownership and so on.

### A return to self-publishing, self-distribution

Over the past year or so there has been a re-emerging interest in people being
able to own their own content again, and not be beholden to corporate interests.
Projects like [Mastodon](http://joinmastodon.org) and [PeerTube](https://joinpeertube.org/)
sprung up around protocols like ActivityPub, and people started to remember how the Internet used to be.
Individuals posting their own stuff to the Internet for other individuals to see.

But none of these projects are focusing on collections of heterogeneous content,
and in the meantime I'd put a lot of thought into how to actually build a site
that satisfies my needs.

I also want to bring back RSS-style feeds as a sharing protocol. ActivityPub is great for instant
pushes of immediate content, but there are so many things which are better-served
by traditional syndication mechanisms. Trickles of serialized content. Long-form
fiction, serial comics, ongoing music projects. Things with continuity. Things
which exist for more than just the here and now.

Also, having spent some time working on large-scale web systems I learned a thing
or two about good practices regarding image handling and CDNs and caching and so on.
Consumer CMSes simply do not pass muster on this.

There are also plenty of static site generators out there, but those are still very
much hands-on, and don't provide a lot of niceties. I wanted to build a system that
gives the best of both worlds between static and dynamic publishing.

At some point I learned about [Flask](http://flask.pocoo.org) and [Jinja](http://jinja.pocoo.org).
These seemed like a perfect basis for how to build the system I wanted to build.

## Design philosophy

I have always been a fan of the UNIX mentality: build small tools that elegantly express
a single function, and design them to operate with one another. To this end, Publ exists
solely to convert URLs into views into content. The URLs are structured to be human-readable
and humane. It is a request-routing system that pretty much just does two things:

1. Decide what to display
2. Decide how to display it

Publ does not include any built-in tools for actually editing content. My reasoning behind
this is that well-structured content can be managed in any number of ways. Personally I want to use
SublimeText and check content files into a repository. Someone else might want a web-based editor;
for that purpose, it would be fairly straightforward to create a tool that maps your server's
filesystem to an online editor view. (For bonus points it could also check changes into git and
otherwise synchronize them upstream.)

Republishing content is a matter of building a tool that handles external content – possibly via RSS/atom, possibly
via parsing external HTML markup — and produces entries for Publ to consume. This could be syndicated via
cron job. This could be pushed in via ActivityPub or some other webhook-type functionality. This could be a web-based
tool where you point it at some random blog entry and go "reblog" and it generates a Publ entry for you
to put wherever you want it.

Finally, following content is the job of a reader. There are a lot of feed readers out there. Most of them
kinda suck. My personal favorite is [Feed on Feeds](http://github.com/fluffy-critter/Feed-on-Feeds);
it's pretty minimal and it does one thing well (read feeds) and mostly gets out of your way. There's a lot
of things it could do better. It would be nice if it differentiated between "stream"-type content (think
Tumblr and breaking-news sites) and long-form content (think comics). It would be nice if it could
integrate into a reblog-type ecosystem.

To that end I have put some thought into making a newer reader-type engine (which I am tentatively calling Subl);
the idea would be that Publ and Subl work together (as part of a publish-subscribe pair), but this isn't really
necessary.

I don't even think that Publ is going to be the best system for most people. There are so many good CMSes out
there. None of them just hit the sweet spot of what I personally want.

I hope to make Publ the system I want, and hopefully someone else also likes it.

## Current work

As you can probably see as of right now, this site is very, very basic. There is
the ability to browse categories, and the ability to read entries within the
categories. Hopefully I'll also have an Atom feed wired up at some point (all of the code to make that possible is already there, I just haven't made the template just yet).

There's actually a lot going on under the hood though. The main thing is that the site
has a dynamic content index, which is backed by the filesystem. Any change you make to
an entry — including moving it, renaming it, changing its category, hiding it, or deleting it — is immediately
reflected in the database.

Well, deletion isn't, but that'd be easy to add. I guess I should add it.

Like a static site generator this is also set up such that the site content is all portable.
I run it as a test instance on my home computer. Once I get the actual hosting set up, in theory all
I need to do is push it to my repo and then pull it to my server. Maybe I could set up a webhook to
tell the server to pull it whenever there's a change! (Yeah, I think I will do that. Eventually.)

There are a bunch of things I need to do before I'm happy with Publ. Here's a partial list of what I'm going to be doing:

### View pagination

Rather than have different template handlers for different kinds of views (date-based, paginated, etc.) I have
a unifying concept for how a view can map to whatever sort of interaction someone might want with content.
Most of this is informed by how Movable Type did things. To that end, each category template will accept a
standard set of parameters for how to restrict the view, and the template itself will know how to paginate
from there. I want to keep the template itself as simple as possible in this regard.

I also strongly believe that pagination URLs should be permanent. So many CMSes think of pagination in terms of
entry offsets; this means that if someone finds a link to a pagination (via search engine, via link, whatever) it
probably doesn't point to the content that was originally intended. So, all pagination will be done based on
attributes that are either absolute (e.g. based on time) or relative to an entry's presumably-indelible characteristics.
And I want the template system to make this easy to write templates around; with the ideas I have in mind, the site
designer won't even have to think about this stuff.

### Entry-relative links

This is kind of a minor thing but having the ability for an entry to link to a sibling entry is pretty
darn important. This is also a thing that I'm not worried about at all. I'd already written the logic in one
of my Publ prototypes, and adapting it to the actual Publ system shouldn't be hard at all.

### Image renditions

This is one of the things I've put the most thought into and still have the most to actually design. I want
it to be easy to pull in image-based content and have it get resized to the renditions that are necessary for
it to look its best. I want to support the `srcset` attribute for multi-resolution support (which is actually pretty easy).
I also want to consider various things that make things nicer for comics, like being able to specify a cropping pattern or
whatever. This should all be easy for the author to configure and more or less transparent. And cache/CDN-friendly by default.

### Making a reasonably-nice-looking site

The site for Publ itself needs to look good enough to make people want to use Publ. Obviously.

The real test will be converting [my main site](http://beesbuzz.biz/) over to Publ.

### Building some useful tools

I will absolutely be building tools for syndicating external content. At its most basic I
*will* be making a section on my site that reflects my latest SoundCloud content, and probably
republishing my Tumblr and whatever. Heck, I might make a section that republishes my
[Mastodon public posts](http://queer.party/@fluffy).

### Access control

This is a really important thing. And probably the most long-term thing of this whole project. I want to support friends-only content.
Privacy is important. This is probably the only thing that's gotten more thought than image renditions. I want to do it and I want
to do it right. And I want to support as many open standards as possible. OpenID at a bare minimum. Probably various OAuth
providers as well.

Supporting ACLs seems pretty straightforward but it's also something that's easy to mess up, and a mess-up can be
catastrophic. So when I do it I want to make sure I do it *absolutely right*.

### Caching

This is pretty easy thanks to [Flask-Cache](https://pythonhosted.org/Flask-Cache/), although there's some subtleties to worry about (especially when ACLs are a thing). So far Publ seems to be pretty lightweight but who knows how that'll change when my sites start getting bigger...

### Comment system

For the foreseeable future I'm fine with using [Disqus](http://disqus.com) for active comment threads, although that has some implications for
private content and of course it kind of flies in the face of the whole "host everything yourself" thing. But comment systems have *huge* implications on scalability and community effort and so on, and there's so many things that need to be put in to make it comfortable for everyone (for example, users being able to ignore other users).

I feel like Disqus comments for immediate responses and reblogs/mutual commentary are the way to go in general. Maybe that's just because I'm used to that from Tumblr.

Having some means of tracking inbound links to see where external commentary is taking place would be good, I guess. Trackbacks were a miserable failure but tracking HTTP `Referer` [sic] headers and showing them on the dashboard would probably be enough.

And on that note...

### Dashboard

Having an admin-viewable error log (for things like content ingest errors). Having stats tracking for entry views, external referrals, analytics in general. These would be good things to have, and shouldn't be too hard to add in. Although scaling is always a concern, especially where analytics are involved.

## Summary

Anyway. I have a lot of plans for this system, and this is just the beginning.

Thanks for reading.
