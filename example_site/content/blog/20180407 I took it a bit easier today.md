Title: I took it a bit easier today
UUID: a333e858-fcfb-4755-9dc3-a338c7411304
Date: 2018-04-07 00:41:50-07:00
Entry-ID: 342

Today I kept myself away from pounding away at Publ. But I did fix an
[entry visibility bug](https://github.com/fluffy-critter/Publ/issues/27), and
also implemented a workaround for [the Dreamhost issue](https://github.com/fluffy-critter/Publ/issues/19).

Oh, and some of my fixes for the visibility bug also led to some code refactoring
that will make view pagination a bit easier to implement, so that's a nice bonus.

I've also put some more thoughts into how view pagination will work. In particular
I think to keep things simple I'll only allow views to sort by oldest or newest;
The only other useful sorting option I can think of is by title and that's not
really all that stable.
