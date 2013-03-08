Spotify WebSocket API [![Build Status](https://travis-ci.org/Hexxeh/spotify-websocket-api.png?branch=master)](https://travis-ci.org/Hexxeh/spotify-websocket-api)
=====================

Getting started
---------------

NOTE: This API will only work with paid Spotify accounts. I'm perfectly fine with this restriction and won't be attempting to circumvent it, nor will I merge patches that do. It'd only end in a game of cat and mouse which is a waste of everyone's time. If you like Spotify, buy a Premium account and tell the industry that it's a great payment model for music.

Firstly, try out the demo script to make sure you've got the dependencies installed properly:

* requests >= 1.0
* ws4py
* protobuf
* lxml

Then you can try one of the example scripts

<pre>
cd examples
python blocking.py &lt;username&gt; &lt;password&gt; album
</pre>

This should show an album title and a list of track titles for it.

Using the API is pretty simple, here's the basics:

<pre>
sp = Spotify("username", "password")
results = sp.search("carly rae jepsen")
for track in results.getTrack()
  print track
</pre>

Experimental client
-------------------

Included is an experimental client called respotify, based on this API. It's almost identical to
despotify-simple in terms of functionality. Be sure to have the following additional dependencies installed:

* cherrypy
* web.py

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

What's implemented?
-------------------

* Login via username/password
* Metadata retrieval (track/album/artist)
* Playlist and rootlist support (add/remove tracks, creation/renaming/deletion)
* Toplists for both regions and users (track/album/artist only)
* Starring/unstarring tracks
* MP3 playback URL retrieval

What's NOT implemented?
-----------------------
* Inbox (not currently supported via the web client it appears)
* Subscribing to playlist updates
* Social functionality

TODO
----

Want to help out? Great! Here's a a list of things that need doing or improving:

* An example graphical client using the API (preferably multi-platform, OSX/Linux)
* Anything from the unimplemented list above

Want to write a library in another language?
--------------------------------------------

If you'd like to help out with this library or write a new one for another language do let me know and pop into #despotify on EFnet. I'm aware of people working on Java and Node.js libraries currently, more are of course welcome.
