Title: Exception case
Path-Alias: /_error
Path-Alias: /error
Path-Alias: /_foo/_bar/baz
Path-Alias: /_login
Date: 2020-08-03 22:59:49-07:00
Entry-ID: 1358
UUID: 8393f616-b08f-55fa-b191-5de9d26fb1b4

This entry should be reachable from [`/_error`](/_error), [`/error`](/error), and [`/_foo/_bar/baz`](/_foo/_bar/baz).
But [`/_alternate`](/_alternate) and [`/_alternate`](/_alternate_index) should still be an error,
and [`/_login`](/_login) should still go to the login page.

