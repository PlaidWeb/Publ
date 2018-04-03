Title: Installing on Dreamhost
Date: 2018-04-03 02:22:07-07:00
Entry-ID: 326
UUID: 45e36baf-9c9a-40bf-9af7-1cbacefda9bd

Dreamhost is kinda-sorta straightforward, once you have a python3 environment working.
Unfortunately, getting the python3 environment working isn't so easy.

Here is more or less what I had to do to get that going.

~~~~~

## Building Python3

I `ssh`ed into my Dreamhost shell account and then downloaded the [Python source distribution](https://www.python.org/downloads/source/)
and then decompressed it:

    $ wget https://www.python.org/ftp/python/3.6.5/Python-3.6.5.tgz
    $ tar xzvf Python-3.6.5.tgz

Then building it was fairly straightforward:

    $ cd Python-3.6.5
    $ ./configure --prefix=$HOME/opt/python-3.6.5 --enable-optimizations
    $ nice -19 make
    $ make install

The `nice -19` is because Dreamhost's process killer kept on killing my build processes due to excessive CPU usage.
Even in the end the unit tests didn't manage to build, but the install process worked anyway.

Then I had to add Python to my environment; I did so by adding the following lines to my `~/.bash_profile`:

    # python3
    export PATH=$HOME/opt/python-3.6.4/bin:$HOME/.local/bin:$PATH

and then also ran that line directly to get python3 in my path. Then finally I could install pipenv via:

    $ pip3 install --user pipenv

and then added the following line to my `~/.bash_profile`:

    eval "$(pipenv --completion)"

## Configuring Publ on Dreamhost

First I set up my domain `publ.beesbuzz.biz` with the following options:

* Domain to host: `publ.beesbuzz.biz`
* Remove WWW from URL
* Web directory: `/home/username/publ.beesbuzz.biz/public`
* Logs directory: `/home/username/logs/publ.beesbuzz.biz` (the default)
* HTTPS (via LetsEncrypt): Yes
* Passenger (Ruby/NodeJS/Python apps only): Yes

After clicking "Fully host now!" and waiting a few minutes I then had a directory with some crap in it.

Next, I installed Publ by doing a `git clone` from github and then moving its files into the right place:

    $ cd publ.beesbuzz.biz
    $ git clone https://github.com/fluffy-critter/Publ
    $ mv Publ/* Publ/.git* .

Then I copied `config.py.dist` to `config.py` and changed `server_name` as appropriate (namely set it to `"publ.beesbuzz.biz"`),
and ran `./setup.sh`.

Finally, to get the static content visible I symlinked it into Dreamhost's `public` directory:

    $ cd public
    $ ln -s ../example_site/static .

At this point I had Publ working with the default site!

If you want to run your own site you will of course want to point the `config.py` values to the appropriate places,
and

## Things left to set up

Setting up CloudFlare or some other CDN should be straightforward but I haven't done it yet. No point until renditions are there, of course.
Chances are it's just as simple as checking the box next to "enable Cloudflare CDN," although for best results it's probably better to
configure static content on its own subdomain. The way to do that would be by setting up hosting like so:

* Domain to host: `static.example.com` (or whatever)
* Enable HTTPS, CDN, yadda yadda yadda
* Web directory: pointed to the `static_directory` value specified in `config.py`

And then in the `config.py` you'd set `static_path` to point to your CDN domain (`static.example.com` in this example).

TODO: Fix this up when image renditions are an actual thing

## Upgrading the code

When code updates, you can simply do a `git pull && ./setup.sh`, which ensures that all the library dependencies are updated as well.
Technically library dependencies will update no matter what but that might take a while which might make your app get killed
on startup until it manages to finish. So it's better to run `./setup.sh` so that the dependencies update before the app tries to restart.

