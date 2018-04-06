Title: Getting started
Date: 2018-04-03 16:24:37-07:00
Entry-ID: 328
UUID: 4dea4c3b-c6ec-4dc0-9f40-b27a91128a60

A guide to starting with Publ.

.....

## Installing system requirements

You'll need Python 3 (at least version 3.6) and [`pipenv`](https://docs.pipenv.org) to be installed.

### macOS

On macOS this is pretty straightforward; after installing [Homebrew](https://brew.sh) you can install these things with:

```bash
brew install python pipenv
```

and then add the following line to your login script (usually `~/.bash_profile`):

```bash
export PATH=$HOME/Library/Python/3.6/bin:$PATH
```

### Other platforms

This should also be possible to do on Linux and Windows; if anyone would like to share how to do it, please [open an issue](http://github.com/fluffy-critter/Publ/issues/new)!

## Obtaining Publ

Now when you open a new terminal you should have pipenv and python3 on your path:

```bash
# which pipenv
/Users/fluffy/Library/Python/3.6/bin/pipenv
# which python3
/usr/local/bin/python3
# python3 --version
Python 3.6.5
```

The next thing to do is to clone a copy of Publ into your own workspace, e.g.

```bash
git clone https://github.com/fluffy-critter/Publ
```

After that you can simply do:

```bash
cd Publ
cp config.py.dist config.py
./setup.sh
./run.sh
```

and now you should have the sample site — namely, an instance of this website — running on `[localhost:5000](http://localhost:5000)`.

## Making your own site

The example site files all live within `example_site/` within the upstream distribution.
If you want to start making your own site, you can create a new site directory (call it, say, `my_site`)
with subdirectories of `templates`, `static`, and `content`, and point your `config.py` at those directories.

At the very basic you'll want to have the following files in `templates`:

    * `index.html` - the category rendering page
    * `feed.xml` - the Atom feed generator
    * `error.html` - the generic error handler
    * `entry.html` - the generic entry renderer

You can reference the example files, or you can try making your own. The [Jinja](http://jinja.pocoo.org) documentation
should be helpful, and for Publ-related extensions look at the [Publ documentation](/manual), particularly the [template format](/template-format) and [entry format](/entry-format).

I do recommend keeping your own content files in a private git repository (separate from Publ itself) as this makes
separating your content from the CMS itself much easier. Also, keep in mind that Publ itself will modify the content
files to add persistent headers, so don't forget to push your Publ-originated changes back to your source repository!

## Updating code

To update the site's code you'll want to do a `git pull` (or uncompress the source snapshot that you're using or whatever)
and then re-run `./setup.sh` to ensure everything is where it needs to be. Then restart any running Publ instance (`setup.sh` does this
automatically for Dreamhost's Passenger setup) and you're good to go!

## Deploying to a webserver

Publ is intended to be run on a containerized platform such as [Heroku](http://heroku.com); the free tier should
be sufficient for at least basic experimentation. Or if you have hosting with a provider that supports Passenger WSGI
you can try deploying there; I have a very basic guide for [installing on Dreamhost](326).

Wherever you end up deploying, you'll need to set your `config.py` values to point to your actual site files and domain name.

If you do end up using Publ, please let me know so that I can check it out — and maybe add it to a list of featured sites!

[TODO](https://github.com/fluffy-critter/Publ/issues/20): Figure out how to best do a Heroku deployment