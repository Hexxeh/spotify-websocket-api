#!/usr/bin/env python

import sys
sys.path.append("../..")
from spotify_web.friendly import Spotify
import cherrypy


class SpotifyURIHandler(object):
    def default(self, uri=None):
        if uri is None:
            raise cherrypy.HTTPError(400, "A paramater was expected but not supplied.")

        spotify = Spotify(sys.argv[1], sys.argv[2])
        track = spotify.objectFromURI(uri)
        if track is None:
            spotify.logout()
            raise cherrypy.HTTPError(404, "Could not find a track with that URI.")

        url = track.getFileURL()
        if not url:
            spotify.logout()
            raise cherrypy.HTTPError(404, "Could not find a track URL for that URI.")

        spotify.logout()
        raise cherrypy.HTTPRedirect(url)

    default.exposed = True

cherrypy.engine.autoreload.unsubscribe()
cherrypy.config.update({"environment": "production"})
cherrypy.quickstart(SpotifyURIHandler())
