from spotify_web.spotify import SpotifyAPI, SpotifyUtil
from spotify_web.proto import mercury_pb2, metadata_pb2
from functools import partial
import sys

class Cache(object):
    def __init__(self, func):
        self.func = func
    def __get__(self, obj, objtype=None):
        if obj is None:
            return self.func
        return partial(self, obj)
    def __call__(self, *args, **kw):
        obj = args[0]
        try:
            cache = obj.__cache
        except AttributeError:
            cache = obj.__cache = {}
        key = (self.func, args[1:], frozenset(kw.items()))
        try:
            res = cache[key]
        except KeyError:
            res = cache[key] = self.func(*args, **kw)
        return res

class SpotifyObject():
	def __str__(self):
		return unicode(self).encode('utf-8')

	def __unicode__(self):
		return self.getName()

	def getID(self):
		return SpotifyUtil.gid2id(self.obj.gid)

	def getURI(self):
		return SpotifyUtil.gid2uri(self.uri_type, self.obj.gid)

class SpotifyMetadataObject(SpotifyObject):
	def __init__(self, spotify, uri = None, obj = None):
		if obj != None:
			self.obj = obj
		else:
			self.obj = spotify.api.metadata_request(uri)
		self.spotify = spotify

	def getName(self):
		return unicode(self.obj.name)

	def getPopularity(self):
		return self.obj.popularity

class SpotifyTrack(SpotifyMetadataObject):
	uri_type = "track"

	def getNumber(self):
		return self.obj.number

	def getDiscNumber(self):
		return self.obj.disc_number

	def getDuration(self):
		return self.obj.duration

	def getFileURL(self):
		resp = self.spotify.api.track_uri(self.obj)

		if resp != False and "uri" in resp:
			return resp["uri"]
		else:
			return False

	@Cache
	def getAlbum(self, nameOnly = False):
		if nameOnly:
			return self.obj.album.name
		else:
			return self.spotify.objectFromInternalObj("album", self.obj.album)

	@Cache
	def getArtist(self, nameOnly = False):
		return self.spotify.objectFromInternalObj("artist", self.obj.artist, nameOnly)

class SpotifyArtist(SpotifyMetadataObject):
	uri_type = "artist"

	def getPortraits(self):
		return Spotify.imagesFromArray(self.obj.portrait)

	def getBiography(self):
		return self.obj.biography.text

	def getNumTracks(self):
		# this means the number of top tracks, really
		return len(self.getTracks(objOnly = True))

	@Cache
	def getRelatedArtists(self, nameOnly = False):
		return self.spotify.objectFromInternalObj("artist", self.obj.related, nameOnly)

	@Cache
	def getTracks(self, objOnly = False):
		top_tracks = []

		for obj in self.obj.top_track:
			if obj.country == self.spotify.api.country:
				top_tracks = obj

		if objOnly:
			return top_tracks.track

		if len(top_tracks.track) == 0:
			return None

		return self.spotify.objectFromInternalObj("track", top_tracks.track)

class SpotifyAlbum(SpotifyMetadataObject):
	uri_type = "album"

	def getLabel(self):
		return self.obj.label

	@Cache
	def getArtist(self, nameOnly = False):
		return self.spotify.objectFromInternalObj("artist", self.obj.artist, nameOnly)

	def getCovers(self):
		return Spotify.imagesFromArray(self.obj.cover)

	def getNumDiscs(self):
		return len(self.obj.disc)

	def getNumTracks(self):
		return len(self.getTracks(objOnly = True))

	@Cache
	def getTracks(self, disc_num = None, objOnly = False):
		track_objs = []

		for disc in self.obj.disc:
			if disc.number == disc_num or disc_num == None:
				track_objs += disc.track

		if objOnly:
			return track_objs

		if len(track_objs) == 0:
			return None

		return self.spotify.objectFromInternalObj("track", track_objs)

class SpotifyPlaylist(SpotifyObject):
	def __init__(self, spotify, uri):
		self.spotify = spotify
		self.obj = spotify.api.playlist_request(uri)
		self.uri = uri

	def getID(self):
		uri_parts = self.uri.split(":")
		if len(uri_parts) == 4:
			return uri_parts[3]
		else:
			return uri_parts[4]

	def getURI(self):
		return self.uri

	def getName(self):
		return "Starred" if self.getID() == "starred" else self.obj.attributes.name

	def getNumTracks(self):
		return self.obj.length

	@Cache
	def getTracks(self):
		track_uris = [item.uri for item in self.obj.contents.items]
		tracks = self.spotify.objectFromURI(track_uris)

		if self.obj.contents.truncated == True:
			tracks_per_call = 100
			start = tracks_per_call
			while start < self.getNumTracks():
				track_uris = [item.uri for item in self.spotify.api.playlist_request(self.uri, start).contents.items]
				tracks += self.spotify.objectFromURI(track_uris)
				start += tracks_per_call

		return tracks


class Spotify():
	def __init__(self, username, password): 
		self.api = SpotifyAPI()
		self.api.connect(username, password)

	def logged_in(self):
		return self.api.logged_in

	def logout(self):
		self.api.disconnect()

	@Cache
	def getPlaylists(self, username = None):
		username = self.api.username if username == None else username
		playlist_uris = []
		if username == self.api.username:
			playlist_uris += ["spotify:user:"+username+":starred"]

		playlist_uris += [playlist.uri for playlist in self.api.playlists_request(username).contents.items]
		return [self.objectFromURI(playlist_uri) for playlist_uri in playlist_uris]

	def search(self, query):
		return self.api.search_request(query)

	def objectFromInternalObj(self, object_type, objs, nameOnly = False):
		if nameOnly:
			return ", ".join([obj.name for obj in objs])

		try:
			uris = [SpotifyUtil.gid2uri(object_type, obj.gid) for obj in objs]
		except:
			uris = SpotifyUtil.gid2uri(object_type, objs.gid)

		return self.objectFromURI(uris)

	def objectFromURI(self, uris):
		if self.logged_in() == False:
			return False

		uris = [uris] if type(uris) != list else uris

		uri_type = SpotifyUtil.get_uri_type(uris[0])
		if uri_type == False:
			return None
		elif uri_type == "playlist":
			results =  [SpotifyPlaylist(self, uri=uri) for uri in uris]
		elif uri_type in ["track", "album", "artist"]:
			uris = [uri for uri in uris if not SpotifyUtil.is_local(uri)]
			objs = self.api.metadata_request(uris)
			objs = [objs] if type(objs) != list else objs
			if uri_type == "track":
				results = [SpotifyTrack(self, obj=obj) for obj in objs]
			elif uri_type == "album":
				results =  [SpotifyAlbum(self, obj=obj) for obj in objs]
			elif uri_type == "artist":
				results =  [SpotifyArtist(self, obj=obj) for obj in objs]
		else:
			return None

		if len(results) == 1:
			return results[0]
		else:
			return results

	@staticmethod
	def imagesFromArray(image_objs):
		images = {}
		for image_obj in image_objs:
			size = str(image_obj.width)
			images[size] = "https://d3rt1990lpmkn.cloudfront.net/" + size + "/" + SpotifyUtil.gid2id(image_obj.file_id)

		return images