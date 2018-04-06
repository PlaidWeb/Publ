## Contributing to Publ

Thank you so much for wanting to help make web publishing better!

While the Publ codebase is small and focused, there are several things to know
about contributing to it.

First, please familiarize yourself with the [code of conduct](CODE_OF_CONDUCT.md),
as it sets out general guidelines for interactions.

## What to be familiar with

This project is built using Python 3, [Flask](http://flask.pocoo.org), and
[Peewee](http://peewee.readthedocs.io). The use of Flask also implies the usage
of [Jinja](http://jinja.pocoo.org). The primary intended format for users to
interact with is Markdown, specifically the flavor expressed by
[Misaka](http://misaka.61924.nl).

## Code quality

Here are some guidelines to how I would like any set of commits to be. (I
fully realize that I myself haven't always held myself to these standards!)

###  Documentability

Any checkin that has a TODO should also reference an issue that reflects the
TODO. The issue should be clear, contain some ideas about how things would be
implemented, how it would fit in, what the requirements for completion of the
issue is, and so on.

Any new functionality must be reflected with a functional test that demonstrates
it working on the live site. If the functionality is regarding indexing or entry
rewriting, a best effort should be made to ensure it still works.

Any new functionality should also come with updates to the appropriate sections
of the manual.

Code should attempt to be self-documenting, but should also be commented to
explain what's going on, at least at a high level.

### Performance and complexity

One-liners or complex list/dict comprehensions are okay as long as they are
clear and idiomatic. Please do not do nested comprehensions; instead, split them
out into separate, clear steps.

No functionality should ever rely on the database being persistent. The database
is disposable and fragile. It is much easier to rescan all the static files on
disk than to try to maintain database integrity, and in some hosting environments
there won't even be a single "the database" -- think of load balancers with every
backing instance running a local SQLite! Thus, anything that relies
on the longevity of the database is itself fragile.

By the same token, the index should only be used to store data that assists in
either finding the entry, or rendering things other than the entry itself. "Hot"
files will always be in the OS's disk cache anyway, and most content is accessed
with a long-tail distribution; if it isn't seen often enough to stay in the disk
cache, the total overhead of keeping it in the database or in memory is worse
than the overhead of rereading it from the ground-truth file when it's needed.

Any performance-optimization work should be done based on where optimization is
needed, and it must show an actual measurable improvement. (Optimizing the
clarity of code, on the other hand, is always welcome!)

### Avoiding "unitaskers"

Functionality should only be added if it would potentially benefit everyone. With
this in mind, any functionality that does only one specific thing should be made
at least flexible or extensible enough that it can also do other, related things.

The templating API should be small and consistent and easy for anyone to remember,
or be easy for anyone to know where to look to understand something.

## Behavior

Be prepared to answer whatever questions people might have about a contribution.
Assume all questions are being made in good faith, and respond in kind.

The same goes for issues.

