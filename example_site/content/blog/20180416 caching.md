Title: Added some basic caching
UUID: cd44010c-39a8-4aa0-b702-3b0d30a68715
Date: 2018-04-16 20:00:00-07:00
Entry-ID: 134

Instead of working on image renditions I decided to try adding in some caching
functionality, and experimented with both `functools.lru_cache` and
[Flask-Cache](https://pythonhosted.org/Flask-Cache/). Neither is a particularly
great solution to caching but they get the job done.

.....

Currently caching uses Flask-Cache for for template resolution and rendered categories,
and `functools.lru_cache` for entry content loading; unfortunately since content
might need to be loaded in the watchdog process (which doesn't run under Flask)
that couldn't go through Flask-Cache.

Unfortunately, this didn't seem to speed anything up on Dreamhost, meaning that
the performance issue there is probably with the fronting Passenger server and
not with I/O limitations on the Publ process.

I haven't done any major performance testing though, I've just gone based on
how it feels. A full analysis can come later. Fortunately, Flask-Cache makes it
pretty easy to turn the cache on or off so measuring it won't be too hard,
I don't think.

I keep saying "image renditions are the next thing I'll work on" and then I end
up not working on them. Must fix that.
