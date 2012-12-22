#!/usr/bin/python

import os, sys
from spotify_web.spotify import SpotifyAPI, SpotifyUtil

def track_uri_callback(sp, result):
	if sys.platform == "darwin":
		os.system("open -a VLC \""+result["uri"]+"\"")
	elif sys.platform == "linux" or sys.platform == "linux2" or sys.platform[:7] == "freebsd":
		os.system("vlc \""+result["uri"]+"\"")
	else:
		print "URL: "+result["uri"]
	sp.disconnect()

def login_callback(sp, logged_in):
	if logged_in:
		uri = sys.argv[3] if len(sys.argv) > 3 else "spotify:track:4a0TeZNKWwoLu4C7H6n95D"
		sp.track_uri(SpotifyUtil.uri2id(uri), track_uri_callback)
	else:
		print "There was an error logging in"

if len(sys.argv) < 3:
	print "Usage: "+sys.argv[0]+" <username> <password> [album URI]"
else:
	sp = SpotifyAPI(login_callback)
	sp.connect(sys.argv[1], sys.argv[2])
