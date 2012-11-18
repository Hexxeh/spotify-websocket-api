spotify-websocket-api
=====================

Getting started
---------------

Currently, Spotify's web client is requiring that you're logged into Facebook in order to login. This is somewhat of a pain to deal with.

So, for now, you'll need to dump a cookie in order to login. The cookie you want is named "sps" and can be found in the request to https://play.spotify.com.

Save the value of that cookie to a file called sps.txt in the same folder as spotify.py in this repo.

You can now run the demo script:

python demo.py


TODO
----

Want to help out? Great! Here's a a list of things that need doing or improving:

* Automating the FB login crap (so that you can login using a username/password and don't have to grab a cookie)
* Search support
* Toplist support
* Radio support
* Queuing and auto-retry for song URL requests (to workaround the rate limiting)
* Playlist editing support
* Track starring
