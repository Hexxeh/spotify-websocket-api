#!/usr/bin/env python

import sys, cherrypy; sys.path.append("..")
from spotify_web.friendly import Spotify

sessions = {}

def get_or_create_session(username, password):
	if username not in sessions:
		spotify = Spotify(username, password)

		if spotify == False:
			return False
		else:
			sessions[username] = spotify
	
	return sessions[username]

def disconnect_sessions():
	for username, session in sessions.items():
		session.logout()

class SpotifyURIHandler(object):
    def default(self,username = None, password = None, uri = None):
       	if uri == None or username == None or password == None:
    		raise cherrypy.HTTPError(400, "A paramater was expected but not supplied.")

    	spotify = get_or_create_session(username, password)
    	if spotify == False:
    		raise cherrypy.HTTPError(403, "Username or password given were incorrect.")

    	track = spotify.objectFromURI(uri)
    	if track == None:
      		raise cherrypy.HTTPError(404, "Could not find a track with that URI.")
      				
      	url = track.getFileURL()
      	if url == False:
      		raise cherrypy.HTTPError(404, "Could not find a track URL for that URI.")

      	raise cherrypy.HTTPRedirect(url)

    default.exposed = True

cherrypy.engine.subscribe("exit", disconnect_sessions)
cherrypy.engine.autoreload.unsubscribe()
cherrypy.quickstart(SpotifyURIHandler())
