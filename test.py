#!/usr/bin/python

from spotify import SpotifyAPI, SpotifyUtil

#We need to store the tracks we're managing, the current lid, and the current track number
currentTracks = []
currentLid = ""
currentTrackI = -1 #Set it to -1 so that we can increment it at the beginning of do_next_queue
currentPlaylistId = ""

def track_uri_callback(sp, result):
	global currentLid, currentTracks, currentTrackI, currentPlaylistId
	if "type" in result and result["type"] == 3:
		Logging.notice("Track is not available. Skipping.")
		do_next_queue(sp)
		return

	#We need to "end" the previous track
	if currentTrackI > 0:	
		#Get the last track
		currentTrack = currentTracks[currentTrackI - 1]
		trackUri = SpotifyUtil.id2uri("track", SpotifyUtil.gid2id(currentTrack.gid))
		sp.track_end(currentLid, 0, 97, trackUri, sp.username, currentPlaylistId, None)

	currentTrack = currentTracks[currentTrackI]
	trackUri = SpotifyUtil.id2uri("track", SpotifyUtil.gid2id(currentTrack.gid))

	lid = result["lid"]
	url = result["uri"]
	currentLid = lid
	print "Got URL for: " + currentTrack.name + " - " + currentTrack.artist[0].name

def track_progress_callback(sp, result):
	sp.track_event(lid, 3, 0)
	sp.track_progress(lid, 500, 97, sp.username, currentPlaylistId, trackUri)
	sp.track_event(lid, 4, 500)
	sp.send_command("sp/echo", ["h"])
	sp.send_command("sp/log", [30, 1, "heartbeat", 77, 77, 2, False])	
	time.sleep(1)	
	do_next_queue(sp)

def multi_track_metadata_callback(sp, tracks):
	global currentTracks
	currentTracks = tracks

def track_metadata_callback(sp, track):
	print track.name

def album_metadata_callback(sp, album):
	print album.name+"\n"
	uris = []
	for track in album.disc[0].track:
		uris.append(SpotifyUtil.gid2uri("track", track.gid))
		sp.track_uri(SpotifyUtil.gid2id(track.gid), "mp3160", track_uri_callback)
	sp.metadata_request(uris, multi_track_metadata_callback)

def playlist_callback(sp, playlist):
	print playlist.attributes.name+"\n"
	uris = []
	for track in playlist.contents.items:
		if SpotifyUtil.get_uri_type(track.uri) != "track":
			continue
		uris.append(track.uri)
	print len(uris)
	
	sp.metadata_request(uris, multi_track_metadata_callback)

def userdata_callback(sp, result):
	global currentPlaylistId
	currentPlaylistId = "spotify:user:hexxeh:playlist:3iNlSln7k9miIMKmNbNf7Q"
	sp.playlist_request(currentPlaylistId, 0, 100, playlist_callback)

def do_next_queue(sp):
	global currentTracks, currentTrackI
	currentTrackI += 1	
	if currentTrackI >= len(currentTracks):	
		print("Done!")	
		return

def login_callback(sp):
	sp.user_info_request(userdata_callback)
	#sp.metadata_request("spotify:album:3OmHoatMS34vM7ZKb4WCY3", album_metadata_callback)
	#sp.metadata_request("spotify:track:1QTmt4xLgL91PiTLMldX7n", track_metadata_callback)
	#sp.playlist_request("spotify:user:hexxeh:playlist:3iyzvzhHmtcw7ruYHmRHF7", 0, 100, playlist_callback)

sp = SpotifyAPI(login_callback)
sp.connect()