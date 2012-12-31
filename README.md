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

Experimental client
-------------------

Included is an experimental client called respotify, based on this API. It's almost identical to
despotify-simple in terms of functionality. Be sure to have the following installed:

* requests 1.0.4
* gevent 1.0 (install from Git, you'll also need cython and libev installed)
* cherrypy

Once you've installed these, you can run the client like this:

<pre>
cd clients/respotify
./respotify.py &lt;username&gt; &lt;password&gt;

                                   _    ___       
                               _  (_)  / __)      
  ____ _____  ___ ____   ___ _| |_ _ _| |__ _   _ 
 / ___) ___ |/___)  _ \ / _ (_   _) (_   __) | | |
| |   | ____|___ | |_| | |_| || |_| | | |  | |_| |
|_|   |_____|___/|  __/ \___/  \__)_| |_|   \__  |
                 |_|                       (____/ 

	
info		shows account information
play		plays the track with given index
help		shows help information
stop		stops any currently playing track
album		view the album for a specific track
quit		quits the application
artist		view the artist for a specific track
list		lists your rootlist or a playlist
uri		lists metadata for a URI (album)
next		plays the next track in the current playlist
current		shows the current playlist we're playing
prev		plays the previous track in the current playlist

>
</pre>

TODO
----

Want to help out? Great! Here's a a list of things that need doing or improving:

* An example graphical client using the API (preferably multi-platform, OSX/Linux)
* Toplist support
* Radio support
