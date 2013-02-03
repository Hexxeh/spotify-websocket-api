#!/usr/bin/env python

import sys
sys.path.append("..")
import signal
from spotify_web.friendly import Spotify
import pygst
pygst.require('0.10')
import gst
import gobject


def sigint(sig, frame):
    global mainloop
    mainloop.quit()


def player_message(bus, msg, player, mainloop):
    if msg.type == gst.MESSAGE_EOS:
        player.set_state(gst.STATE_NULL)
        mainloop.quit()
    elif msg.type == gst.MESSAGE_ERROR:
        player.set_state(gst.STATE_NULL)
        print msg.parse_error()

if len(sys.argv) < 3:
    print "Usage: " + sys.argv[0] + " <username> <password> [track URI]"
else:

    sp = Spotify(sys.argv[1], sys.argv[2])
    mainloop = gobject.MainLoop()

    player = gst.parse_launch('uridecodebin name=uridecode ! autoaudiosink')

    bus = player.get_bus()
    bus.add_signal_watch()
    bus.connect('message', player_message, player, mainloop)

    uri = sys.argv[3] if len(sys.argv) > 3 else "spotify:track:6NwbeybX6TDtXlpXvnUOZC"
    track = sp.objectFromURI(uri)

    print ','.join([a.getName() for a in track.getArtists()]) + ' - ' + track.getName()

    mp3_uri = track.getFileURL()
    player.get_by_name('uridecode').set_property('uri', mp3_uri)
    player.set_state(gst.STATE_PLAYING)

    signal.signal(signal.SIGINT, sigint)
    mainloop.run()

    sp.logout()
