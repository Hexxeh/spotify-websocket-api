#!/usr/bin/env python

import sys
sys.path.append("..")
from spotify_web.spotify import SpotifyAPI, SpotifyUtil

if len(sys.argv) < 4:
    print "Usage: "+sys.argv[0]+" <username> <password> <action> [URI]"
    sys.exit(1)

action = sys.argv[3]

sp = SpotifyAPI()
sp.connect(sys.argv[1], sys.argv[2])


def display_playlist(playlist):
    print playlist.attributes.name+"\n"

    if playlist.length > 0:
        track_uris = [track.uri for track in playlist.contents.items if not SpotifyUtil.is_local(track.uri)]
        tracks = sp.metadata_request(track_uris)
        for track in tracks:
            print track.name
    else:
        print "no tracks"

    print "\n"

if action == "track":
    uri = sys.argv[4] if len(sys.argv) > 4 else "spotify:track:3IKSCoHEblCE60IKr4SVNd"

    track = sp.metadata_request(uri)
    print track.name

elif action == "album":
    uri = sys.argv[4] if len(sys.argv) > 4 else "spotify:album:3OmHoatMS34vM7ZKb4WCY3"

    album = sp.metadata_request(uri)
    print album.name+" - "+album.artist[0].name+"\n"

    uris = [SpotifyUtil.gid2uri("track", track.gid) for track in album.disc[0].track]
    tracks = sp.metadata_request(uris)
    for track in tracks:
        print track.name

elif action == "playlists":
    username = sys.argv[4] if len(sys.argv) > 4 else sp.username

    playlist_uris = [playlist.uri for playlist in sp.playlists_request(username).contents.items]
    playlists = [sp.playlist_request(playlist_uri) for playlist_uri in playlist_uris]

    for playlist in playlists:
        display_playlist(playlist)

elif action == "playlist":
    uri = sys.argv[4] if len(sys.argv) > 4 else "spotify:user:topsify:playlist:1QM1qz09ZzsAPiXphF1l4S"

    playlist = sp.playlist_request(uri)
    display_playlist(playlist)

elif action == "tracks_toplist":
    top_tracks = sp.toplist_request("tracks")
    print top_tracks

elif action == "restriction":
    uri = sys.argv[4] if len(sys.argv) > 4 else "spotify:track:3IKSCoHEblCE60IKr4SVNd"

    track = sp.metadata_request(uri)
    resp = sp.track_uri(track)

    if False != resp and "uri" in resp:
        print "Track is available!"
    else:
        print "Track is NOT available! Double-check this using the official client"

elif action == "newplaylist":
    name = sys.argv[4] if len(sys.argv) > 4 else "foobar"
    uri = sp.new_playlist(name)
    print uri
