Title: Accept tests in the subdirectory
Date: 2025-10-19 22:33:30-07:00
Entry-ID: 2244
UUID: 9c260b63-4103-59a3-9f30-938469997aa4

Here are some templates and their expected MIME types:

* [test.html](test.html) `text/html` --- should fallback
* [test.json](test.json) `application/json` --- should fallback
* [test.txt](test.txt) `text/plain` --- should fallback
* [test.xml](test.xml) `application/xml` --- should use the subdir version
* [test.css](test.css) `style/css` --- should use the subdir version
* [bloop.plap](bloop.plap) `application/plap-override` --- should use subdir, and override the MIME type
* [test.xyzzy](test.xyzzy) `application/plugh` --- should fallback