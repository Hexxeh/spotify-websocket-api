spotify-websocket-api
=====================

Getting started
---------------

Firstly, try out the demo script to make sure you've got the dependencies installed properly:

<pre>
python blocking.py &lt;username&gt; &lt;password&gt; album
</pre>

This should show an album title and a list of track titles for it.

Using the API is pretty simple, here's the basics:

<pre>
sp = SpotifyAPI(login_callback)
sp.connect(username, password)
</pre>

TODO
----

Want to help out? Great! Here's a a list of things that need doing or improving:

* An example client using the API (preferably multi-platform, OSX/Linux)
* Toplist support
* Radio support
