Title: Installing on Dreamhost
Date: 2018-04-03 02:22:07-07:00
Entry-ID: 326
UUID: 45e36baf-9c9a-40bf-9af7-1cbacefda9bd

A quick guide to getting Publ running on Dreamhost's Passenger environment

.....

Dreamhost is kinda-sorta straightforward, once you have a python3 environment working. However, setting up python3 isn't
quite obvious, and [Dreamhost's own instructions](https://help.dreamhost.com/hc/en-us/articles/115000702772-Installing-a-custom-version-of-Python-3)
are incomplete and don't include [`pipenv`](https://docs.pipenv.org) (which, to be fair, is a fairly recent addition to the ecosystem, having only appeared around ).

## Building Python3

I `ssh`ed into my Dreamhost shell account and then downloaded the [Python source distribution](https://www.python.org/downloads/source/)
and then decompressed it:

```bash
wget https://www.python.org/ftp/python/3.6.5/Python-3.6.5.tgz
tar xzvf Python-3.6.5.tgz
```

Then building it was fairly straightforward:

```bash
cd Python-3.6.5
./configure --prefix=$HOME/opt/python-3.6.5 --enable-optimizations
nice -19 make build_all
make install
```

The `nice -19` is to reduce the chances that Dreamhost's process killer kicks in for the build, and `build_all` builds Python without building unit tests (which Dreamhost's process killer severely dislikes).

Then I had to add Python to my environment; I did so by adding the following lines to my `~/.bash_profile`:

```bash
# python3
export PATH=$HOME/opt/python-3.6.5/bin:$HOME/.local/bin:$PATH
```

and then also ran that line directly to get python3 in my path. Then finally I could install pipenv via:

```bash
pip3 install --user pipenv
```

and then added the following line to my `~/.bash_profile`:

```bash
eval "$(pipenv --completion)"
```

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

```bash
cd publ.beesbuzz.biz
git clone https://github.com/fluffy-critter/Publ
mv Publ/* Publ/.git* .
```

Then I copied `config.py.dist` to `config.py` and changed `server_name` as appropriate (namely set it to `"publ.beesbuzz.biz"`),
and ran `./setup.sh`.

Finally, to get the static content visible I symlinked it into Dreamhost's `public` directory: (this isn't strictly necessary but it helps with performance)

```bash
cd public
ln -sf ../example_site/static .
```

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

TODO: Fix this up when image renditions are an actual thing ([issue 9](http://github.com/fluffy-critter/Publ/issues/9))

## Upgrading the code

When code updates, you can simply do a `git pull && ./setup.sh`, which ensures that all the library dependencies are updated as well.
Technically library dependencies will update no matter what but that might take a while which might make your app get killed
on startup until it manages to finish. So it's better to run `./setup.sh` so that the dependencies update before the app tries to restart.

