#!/usr/bin/python

import sys
from spotify import SpotifyAPI, SpotifyUtil

def track_callback(sp, tracks):
	for track in tracks:
		print track.name
	sp.disconnect()

def album_callback(sp, album):
	print album.name+"\n"
	uris = [SpotifyUtil.gid2uri("track", track.gid) for track in album.disc[0].track]	
	sp.metadata_request(uris, track_callback)

def login_callback(sp):
	uri = sys.argv[1] if len(sys.argv) > 1 else "spotify:album:3OmHoatMS34vM7ZKb4WCY3"
	sp.metadata_request(uri, album_callback)

sp = SpotifyAPI(login_callback)
sp.connect()
