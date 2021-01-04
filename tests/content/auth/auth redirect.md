Title: Redirect for unauthorized entry
Auth: foo
Path-Alias: /alias/u1
Path-Mount: /alias/u1m
Path-Alias: /alias/u1i archive
Path-Mount: /alias/u1a _alternate
Date: 2020-02-22 14:46:21-08:00
Entry-ID: 954
UUID: 4ba25714-eaa4-5447-a737-ddb8ee1c9f8d

* [/alias/u1](/alias/u1) should redirect but only if the user is authorized.
* [/alias/u1m](/alias/u1m) should render directly, but only if the user is authorized.
* [/alias/u1i](/alias/u1i) should redirect to archive but only if the user is authorized.
* [/alias/u1a](/alias/u1a) should render with alternate but only if the user is authorized.
