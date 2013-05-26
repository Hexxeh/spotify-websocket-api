#!/usr/bin/env python

import argparse
import getpass
import sys
sys.path.append("../..")
from spotify_web.friendly import Spotify, SpotifyTrack, SpotifyUserlist
from threading import Thread, Lock, Event
from mpd import MPDClient
import os
import subprocess

playing_playlist = None
current_playlist = None
uri_resolver = None


class LockableMPDClient(MPDClient):
    def __init__(self, use_unicode=False):
        super(LockableMPDClient, self).__init__()
        self.use_unicode = use_unicode
        self._lock = Lock()

    def acquire(self):
        self._lock.acquire()

    def release(self):
        self._lock.release()

    def __enter__(self):
        self.acquire()

    def __exit__(self, type, value, traceback):
        self.release()

client = LockableMPDClient()


def header():
    os.system("clear")
    print """                                   _    ___
                               _  (_)  / __)
  ____ _____  ___ ____   ___ _| |_ _ _| |__ _   _
 / ___) ___ |/___)  _ \ / _ (_   _) (_   __) | | |
| |   | ____|___ | |_| | |_| || |_| | | |  | |_| |
|_|   |_____|___/|  __/ \___/  \__)_| |_|   \__  |
                 |_|                       (____/

    """


def display_playlist(playlist=None):
    if current_playlist is None and playlist is None:
        return

    playlist = current_playlist if playlist is None else playlist

    print playlist.getName()+"\n"

    if playlist.getNumTracks() == 0:
        print "No tracks currently in playlist"
    else:
        with client:
            status = client.status()
        playing_index = int(status["song"]) + 1 if "song" in status else -1
        index = 1
        tracks = playlist.getTracks()
        for track in tracks:
            status
            prefix = " * " if playlist == playing_playlist and index == playing_index and status["state"] == "play" else "   "
            print prefix + "[" + str(index) + "] " + track.getName() + " - " + track.getArtists(nameOnly=True)
            index += 1


def set_current_playlist(playlist):
    global current_playlist
    current_playlist = playlist
    display_playlist()


def command_list(*args):
    global rootlist
    global current_playlist

    rootlist = spotify.getPlaylists()

    if len(*args) == 0 or args[0][0] == "":
        print "Playlists\n"
        index = 1
        for playlist in rootlist:
            print " ["+str(index)+"] "+playlist.getName()
            index += 1
    else:
        try:
            if len(rootlist) >= int(args[0][0]):
                playlist_index = int(args[0][0])-1
                set_current_playlist(rootlist[playlist_index])
        except:
            command_list([])


def command_uri(*args):
    if len(*args) > 0:
        uri = args[0][0]

        obj = spotify.objectFromURI(uri)
        if obj is None:
            print "Invalid URI"
            return

        if isinstance(obj, SpotifyTrack):
            obj = SpotifyUserlist(spotify, obj.getName(), [obj])

        set_current_playlist(obj)


def command_album(*args):
    if args[0][0] == "" or current_playlist is None:
        return

    index = int(args[0][0])-1
    if current_playlist.getNumTracks() < index:
        return

    album = current_playlist.getTracks()[index].getAlbum()
    set_current_playlist(album)


def command_artist(*args):
    if args[0][0] == "" or current_playlist is None:
        return

    index = int(args[0][0])-1
    if current_playlist.getNumTracks() < index:
        return

    artist = current_playlist.getTracks()[index].getArtists()[0]
    set_current_playlist(artist)


def command_search(*args):
    if len(*args) == 0 or args[0][0] == "":
        return

    query = " ".join(args[0])

    results = spotify.search(query, query_type="tracks")
    tracks = results.getTracks()

    if len(tracks) == 0:
        print "No tracks found!"
        return

    set_current_playlist(results)


def command_play(*args):
    if len(*args) == 0 or args[0][0] == "":
        return

    try:
        play_index = int(args[0][0])-1
    except:
        return

    global playing_playlist
    playing_playlist = current_playlist
    with client:
        client.clear()
        for track in current_playlist.getTracks():
            client.add("http://localhost:8080/?uri="+track.getURI())
        client.play(play_index)

    display_playlist()


def command_stop(*args):
    with client:
        client.stop()
    display_playlist()


def command_next(*args):
    with client:
        client.next()
    display_playlist()


def command_prev(*args):
    with client:
        status = client.status()
    if "song" in status:
        if status["song"] != "0":
            client.previous()
        elif status["state"] == "play":
            client.stop()
    display_playlist()


def command_info(*args):
    print "Username: " + spotify.api.username
    print "Account type: " + spotify.api.account_type
    print "Country: " + spotify.api.country
    print "Connected to " + spotify.api.settings["wss"].replace("wss://", "").replace(":443", "").replace("/", "")


def command_help(*args):
    for k, v in command_map.items():
        print k+"\t\t"+v[1]

quitting = False


def command_quit(*args):
    spotify.logout()
    global quitting
    quitting = True


def command_current_playlist(*args):
    display_playlist(playing_playlist)

command_map = {
    "search": (command_search, "search for tracks"),
    "artist": (command_artist, "view the artist for a specific track"),
    "album":  (command_album, "view the album for a specific track"),
    "stop": (command_stop, "stops any currently playing track"),
    "play": (command_play, "plays the track with given index"),
    "next": (command_next, "plays the next track in the current playlist"),
    "prev": (command_prev, "plays the previous track in the current playlist"),
    "current": (command_current_playlist, "shows the current playlist we're playing"),
    "uri": (command_uri, "lists metadata for a URI (album)"),
    "list": (command_list, "lists your rootlist or a playlist"),
    "info": (command_info, "shows account information"),
    "help": (command_help, "shows help information"),
    "quit": (command_quit, "quits the application"),
}


def command_loop():
    header()
    command_help()
    while False == spotify.api.disconnecting and False == quitting:
        sys.stdout.write("\n> ")
        sys.stdout.flush()
        command = raw_input().split(" ")
        command_name = command[0]

        header()
        if command_name in command_map:
            command_map[command_name][0](command[1:])
        else:
            command_help()

heartbeat_marker = Event()


def heartbeat_handler():
    while client is not None:
        with client:
            client.status()
        heartbeat_marker.wait(timeout=15)


if __name__ == '__main__':

    parser = argparse.ArgumentParser(description='Command line Spotify client')
    parser.add_argument('username', help='Your spotify username')
    parser.add_argument('password', nargs='?', default=None,
                        help='<Optional> your spotify password')

    args = parser.parse_args()

    if args.password is None:
        args.password = getpass.getpass("Please enter your Spotify password")

    spotify = Spotify(args.username, args.password)
    if spotify.logged_in():
        os.system("kill `pgrep -f respotify-helper` &> /dev/null")
        uri_resolver = subprocess.Popen([sys.executable, "respotify-helper.py",
                                        args.username, args.password])
        with client:
            client.connect(host="localhost", port="6600")
        Thread(target=heartbeat_handler).start()
        command_loop()
        os.system("clear")
        with client:
            client.clear()
            client.disconnect()
            client = None
            heartbeat_marker.set()
        uri_resolver.kill()
    else:
        print "Login failed"
        sys.exit(1)
