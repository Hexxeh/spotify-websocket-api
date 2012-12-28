from spotify_web.spotify import SpotifyAPI, SpotifyUtil
from spotify_web.proto import mercury_pb2, metadata_pb2
import sys

class SpotifyObject():
	def __init__(self, sp, obj):
		self.obj = obj
		self.sp = sp

	def __str__(self):
		return self.obj.name

	def getID(self):
		return SpotifyUtil.gid2id(self.obj.gid)

	def getURI(self):
		return SpotifyUtil.gid2uri(self.uri_type, self.obj.gid)

	def getName(self):
		return self.obj.name	

	def getPopularity(self):
		return self.obj.popularity

class SpotifyTrack(SpotifyObject):
	uri_type = "track"

	def getNumber(self):
		return self.obj.number

	def getDiscNumber(self):
		return self.obj.disc_number

	def getDuration(self):
		return self.obj.duration

	def getFileURL(self):
		resp = self.sp.track_uri(self.obj)

		if "uri" in resp:
			return resp["uri"]
		else:
			return False

	def getAlbum(self, nameOnly = False):
		if nameOnly:
			return self.obj.album.name
		else:
			album_obj = self.sp.metadata_request(SpotifyUtil.gid2uri("album", self.obj.album.gid))
			return SpotifyAlbum(self.sp, album_obj)

	def getArtist(self, nameOnly = False):
		return Spotify.artistsFromArray(self.sp, self.obj.artist, nameOnly)

class SpotifyArtist(SpotifyObject):
	uri_type = "artist"

	def getPortraits(self):
		return Spotify.imagesFromArray(self.obj.portrait)

	def getBiography(self):
		return self.obj.biography.text

	def getRelatedArtists(self, nameOnly = False):
		return Spotify.artistsFromArray(self.sp, self.obj.related, nameOnly)

	def getTopTracks(self):
		top_tracks = None

		for obj in self.obj.top_track:
			if obj.country == self.sp.country:
				top_tracks = obj

		if top_tracks == None:
			return False

		return Spotify.tracksFromArray(self.sp, top_tracks.track)

class SpotifyAlbum(SpotifyObject):
	uri_type = "album"

	def getLabel(self):
		return self.obj.label

	def getArtist(self, nameOnly = False):
		return Spotify.artistsFromArray(self.sp, self.obj.artist, nameOnly)

	def getCovers(self):
		return Spotify.imagesFromArray(self.obj.cover)

	def getNumDiscs(self):
		return len(self.obj.disc)

	def getTracks(self, disc_num = None):
		track_objs = []

		for disc in self.obj.disc:
			if disc.number == disc_num or disc_num == None:
				track_objs += disc.track

		if len(track_objs) == 0:
			return None

		return Spotify.tracksFromArray(self.sp, track_objs)

class Spotify():
	def __init__(self, username, password): 
		self.api = SpotifyAPI()
		self.api.connect(username, password)

	def logged_in(self):
		return self.api.logged_in

	def logout(self):
		self.api.disconnect()

	def objectFromURI(self, uri):
		if self.logged_in() == False:
			return False

		if SpotifyUtil.get_uri_type(uri) == False:
			return None

		obj = self.api.metadata_request(uri)

		if type(obj) == metadata_pb2.Track:
			return SpotifyTrack(self.api, obj)
		if type(obj) == metadata_pb2.Album:
			return SpotifyAlbum(self.api, obj)
		if type(obj) == metadata_pb2.Artist:
			return SpotifyArtist(self.api, obj)
		else:
			return None

	@staticmethod
	def tracksFromArray(sp, track_objs):
		track_uris = [SpotifyUtil.gid2uri("track", track.gid) for track in track_objs]
		track_objs = sp.metadata_request(track_uris)

		if type(track_objs) == metadata_pb2.Track:
			return SpotifyTrack(sp, track_objs)
		else:
			tracks = [SpotifyTrack(sp, track_obj) for track_obj in track_objs]
			return tracks

	@staticmethod
	def artistsFromArray(sp, artist_objs, nameOnly):
		if nameOnly:
			return ", ".join([artist.name for artist in artist_objs])
		else:
			artist_uris = [SpotifyUtil.gid2uri("artist", artist.gid) for artist in artist_objs]
			artist_objs = sp.metadata_request(artist_uris)

			if type(artist_objs) == metadata_pb2.Artist:
				return SpotifyArtist(sp, artist_objs)
			else:
				artists = [SpotifyArtist(sp, artist_obj) for artist_obj in artist_objs]
				return artists

	@staticmethod
	def imagesFromArray(image_objs):
		images = {}
		for image_obj in image_objs:
			print image_obj.size
			size = image_obj.width
			images[size] = "https://d3rt1990lpmkn.cloudfront.net/" + str(size) + "/" + SpotifyUtil.gid2id(image_obj.file_id)

		return images