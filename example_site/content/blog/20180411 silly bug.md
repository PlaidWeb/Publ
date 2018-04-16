Title: The silliest Publ bug so far
Date: 2018-04-11 21:22:50-07:00
Entry-ID: 225
UUID: b0e0781a-27bb-4d39-9bf7-d94331c9c109

So I was trying to figure out why new entries weren't appearing in indexes until
things restarted. I thought it might be a caching thing, but editing entries caused
them to update instantly. So then I thought it might be an index thing, like maybe
something silly with how SQLite handles timezone-aware DateTimes, so I overhauled
the date handling so that it separated out `display_date` from `entry_date`, but
that didn't help either. Then I looked closely at the database before and after
restarting the process, and that didn't help. And then I made sure my queries
were using the right timezone, and that didn't help.

Then I had one of those moments where I realized what I'd done wrong with such
sudden clarity that I couldn't help but yell at myself a little.

.....

The code was in the query generator. The bad code:

```python
where_entry_visible = (
    (model.Entry.status == model.PublishStatus.PUBLISHED) |
    (
        (model.Entry.status == model.PublishStatus.SCHEDULED) &
        (model.Entry.entry_date <= arrow.utcnow().datetime)
    )
)
```

The correct, working version is, instead:

```python
def where_entry_visible():
    return (
        (model.Entry.status == model.PublishStatus.PUBLISHED) |
        (
            (model.Entry.status == model.PublishStatus.SCHEDULED) &
            (model.Entry.entry_date <= arrow.utcnow().datetime)
        )
    )
```

See if you can figure out what the problem was.

(I guess that strictly-speaking it *was* a caching bug, just nowhere close to where I thought it was!)

...

ANYway. While I Was doing that I also noticed I'd made a regression in the
entry scanner which was causing the weird old `Entry-ID` generation behavior
to happen when an entry got its entry ID deleted. That turned out to be me
not thinking things through with the order of operations on how, exactly, the
map-to-filepath logic worked. Which used a silly shortcut that didn't actually
buy anything except headaches, so I made the code a bit more explicit in how
it works. And I also added some comments so future-me might have a chance of
understanding it.

 I feel a bit silly for making such a rookie mistake, and now there's some
extra date handling stuff that's probably not strictly necessary although it doesn't
hurt, either, right? And who knows, maybe SQLite or some other future DBMS
does have trouble with comparing TZ-enabled datetimes anyway. Data normalization
is generally a good thing.
