#!/usr/bin/python

import sys
from spotify import SpotifyAPI, SpotifyUtil

def track_uri_callback(sp, result):
	print str(result)

def multi_track_metadata_callback(sp, tracks):
	for track in tracks:
		print track.name

def track_metadata_callback(sp, track):
	print track.name

def album_metadata_callback(sp, album):
	print album.name+"\n"
	uris = []
	for track in album.disc[0].track:
		uris.append(SpotifyUtil.id2uri("track", SpotifyUtil.gid2id(track.gid)))
		#sp.track_uri(SpotifyUtil.gid2id(track.gid), "mp3160", track_uri_callback)

	sp.metadata_request(uris, multi_track_metadata_callback)

def playlist_callback(sp, playlist):
	print playlist.attributes.name+"\n"
	uris = []
	for track in playlist.contents.items:
		uris.append(track.uri)
	
	sp.metadata_request(uris, multi_track_metadata_callback)

def userdata_callback(sp, result):
	print result["user"]

def login_callback(sp):
	#sp.user_info_request(userdata_callback)
	#sp.metadata_request("spotify:album:3OmHoatMS34vM7ZKb4WCY3", album_metadata_callback)
	#sp.metadata_request("spotify:track:1QTmt4xLgL91PiTLMldX7n", track_metadata_callback)
	sp.playlist_request("spotify:user:topsify:playlist:1QM1qz09ZzsAPiXphF1l4S", 0, 100, playlist_callback)

sp = SpotifyAPI(login_callback)
sp.auth()
sp.connect()