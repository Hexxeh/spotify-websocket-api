#!/usr/bin/env python

import sys, unittest
from spotify_web.friendly import Spotify

class SpotifyTest(unittest.TestCase):
	def setUp(self):
		self.spotify = Spotify(USERNAME, PASSWORD)
		print self.spotify.logged_in()
		if self.spotify.logged_in() != True:
			print "Login failed"

	def test_get_track_by_uri(self):
		test_uris = {
			"spotify:track:4DoiEk7AaubTkIkYencvx7": {
				"title": "Figure 8",
				"artist": "Ellie Goulding",
				"album": "Halcyon"
			},
			"spotify:track:6Qmmzzo9Sdk0QZp0dfLpGk": {
				"title": "Commander",
				"artist": "Kelly Rowland, David Guetta",
				"album": "Commander"
			}
		}

		for uri, reference in test_uris.items():
			track = self.spotify.objectFromURI(uri)
			self.assertEqual(reference["title"], track.getName())
			self.assertEqual(reference["artist"], track.getArtists(nameOnly = True))
			self.assertEqual(reference["album"], track.getAlbum(nameOnly = True))

if __name__ == '__main__':
	if len(sys.argv) < 3:
		print "Usage: test.py <username> <password>"
		sys.exit(1)

	USERNAME = sys.argv[1]
	PASSWORD = sys.argv[2]
	sys.argv = sys.argv[2:]
	unittest.main()