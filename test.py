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
	print playlist.attributes.name
	uris = []
	for track in playlist.contents.items:
		uris.append(track.uri)
	
	#sp.metadata_request(uris, multi_track_metadata_callback)


def playlists_callback(sp, playlists):
	for playlist in playlists.contents.items:
		sp.playlist_request(playlist.uri, 0, 100, playlist_callback)

def userdata_callback(sp, result):
	print result["user"]

def generic_callback(sp, result):
	print result

def login_callback(sp):
	#sp.user_info_request(userdata_callback)
	#sp.metadata_request("spotify:album:3OmHoatMS34vM7ZKb4WCY3", album_metadata_callback)
	#sp.metadata_request("spotify:track:1QTmt4xLgL91PiTLMldX7n", track_metadata_callback)
	#sp.playlist_request("spotify:user:topsify:playlist:1QM1qz09ZzsAPiXphF1l4S", 0, 100, playlist_callback)
	#sp.playlists_request("hexxeh", 0, 100, playlists_callback)
	#sp.search_request("norah jones", generic_callback)
	sp.set_starred("spotify:track:0Cvjlph1WGbwZY1PlMEtJY", False, generic_callback)

if len(sys.argv) < 3:
	print "Usage: "+sys.argv[0]+" <username> <password> [album URI]"
else:
	sp = SpotifyAPI(login_callback)
	sp.connect(sys.argv[1], sys.argv[2])
