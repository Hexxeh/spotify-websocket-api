#!/usr/bin/env python

import sys
sys.path.append("..")
from spotify_web.friendly import Spotify
import cherrypy


sessions = {}


def get_or_create_session(username, password):
    if username not in sessions:
        spotify = Spotify(username, password)

        if not spotify:
            return False
        else:
            sessions[username] = spotify

    return sessions[username]


def disconnect_sessions():
    for username, session in sessions.items():
        session.logout()


class SpotifyURIHandler(object):
    def default(self, username=None, password=None, uri=None, action="proxymp3"):
        if uri is None or username is None or password is None:
            raise cherrypy.HTTPError(400, "A paramater was expected but not supplied.")

        spotify = get_or_create_session(username, password)
        if not spotify:
            raise cherrypy.HTTPError(403, "Username or password given were incorrect.")

        track = spotify.objectFromURI(uri)
        if track is None:
            raise cherrypy.HTTPError(404, "Could not find a track with that URI.")

        if action == "proxymp3":
            url = track.getFileURL()
            if not url:
                raise cherrypy.HTTPError(404, "Could not find a track URL for that URI.")
        elif action == "proxycover":
            covers = track.getAlbum().getCovers()
            url = covers["640"]
        else:
            raise cherrypy.HTTPError(400, "An invalid action was requested.")

        raise cherrypy.HTTPRedirect(url)

    default.exposed = True

cherrypy.engine.subscribe("exit", disconnect_sessions)
cherrypy.engine.autoreload.unsubscribe()
cherrypy.config.update({"environment": "production"})
cherrypy.quickstart(SpotifyURIHandler())
