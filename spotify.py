#!/usr/bin/python

import base64, binascii, httplib, json, pprint, re, string, sys, time, urllib
from ws4py.client.threadedclient import WebSocketClient

sys.path.append("proto")
import mercury_pb2, metadata_pb2
import playlist4changes_pb2, playlist4content_pb2
import playlist4issues_pb2, playlist4meta_pb2
import playlist4ops_pb2

base62 = "0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"

class Logging():
	log_level = 2

	@staticmethod
	def debug(str):
		if Logging.log_level >= 3:
			print "[DEBUG] " + str

	@staticmethod
	def notice(str):
		if Logging.log_level >= 2:
			print "[NOTICE] " + str

	@staticmethod
	def warn(str):
		if Logging.log_level >= 1:
			print "[WARN] " + str

	@staticmethod
	def error(str):
		if Logging.log_level >= 0:
			print "[ERROR] " + str

class SpotifyClient(WebSocketClient):
	def set_api(self, api):
		self.api_object = api

	def opened(self):
		self.api_object.login()

	def closed(self, code, reason=None):
		Logging.error("Connection closed, code %d reason %s" % (code, reason))

	def received_message(self, m):
		self.api_object.recv_packet(m)

class SpotifyUtil():
	@staticmethod
	def gid2id(gid):
		return binascii.hexlify(gid)

	@staticmethod
	def id2uri(uritype, v):
		res = []
		v = int(v, 16)
		while v > 0:
		    res = [v % 62] + res
		    v = v / 62
		id = ''.join([base62[i] for i in res])
		return "spotify:"+uritype+":"+id

	@staticmethod
	def uri2id(uri):
		v = 0
		s = uri.split(":")[2]
		for c in s:
		    v = v * 62 + base62.index(c)
		return hex(v)[2:-1]

	@staticmethod
	def get_uri_type(uri):	
		return uri.split(":")[1]

	@staticmethod
	def metadata_resp_to_obj(resp):
		header = mercury_pb2.MercuryReply()
		header.ParseFromString(base64.decodestring(resp[0]))

		if header.status_message == "vnd.spotify/mercury-mget-reply":
			mget_reply = mercury_pb2.MercuryMultiGetReply()
			mget_reply.ParseFromString(base64.decodestring(resp[1]))
			items = []
			for reply in mget_reply.reply:
				item = SpotifyUtil.parse_metadata_item(reply.content_type, reply.body)
				items.append(item)
			return items
		else:
			return SpotifyUtil.parse_metadata_item(header.status_message, base64.decodestring(resp[1]))

	@staticmethod
	def parse_metadata_item(content_type, body):
		if content_type == "vnd.spotify/metadata-album":
			obj = metadata_pb2.Album()
		elif content_type == "vnd.spotify/metadata-track":
			obj = metadata_pb2.Track()
		else:
			Logging.error("Unrecognised metadata type " + content_type)
			return False

		obj.ParseFromString(body)
		return obj

	@staticmethod
	def parse_playlist(resp):
		obj = playlist4changes_pb2.ListDump()
		res = base64.decodestring(resp[1])
		obj.ParseFromString(res)

class SpotifyAPI():
	def __init__(self, login_callback_func = None):
		self.auth_server = "play.spotify.com"

		self.username = None
		self.password = None
		self.account_type = None
		self.country = None

		self.settings = None

		self.ws = None
		self.seq = 0
		self.cmd_callbacks = {}
		self.login_callback = login_callback_func

	def auth(self):
		if self.settings != None:
			Logging.warn("You must only authenticate once per API object")
			return False

		with open ("sps.txt", "r") as myfile:
			sps=myfile.read().replace('\n', '')

		conn = httplib.HTTPSConnection(self.auth_server)
		headers = {
			"Cookie": "sps="+sps
		}
		conn.request("GET", "/", headers = headers)
		response = conn.getresponse()
		data = response.read()
		conn.close()

		rx = re.compile("Spotify.Web.App.initialize\((.*), null\);")
		r = rx.search(data)

		if not r or len(r.groups()) < 1:
			Logging.error("There was a problem authenticating, no auth JSON found")
			return False

		settings_str = r.groups()[0]
		self.settings = json.loads(settings_str)

	def populate_userdata_callback(self, sp, resp):
		self.username = resp["user"]
		self.country = resp["country"]
		self.account_type = resp["catalogue"]

	def logged_in(self, sp, resp):
		self.user_info_request(self.populate_userdata_callback)
		self.login_callback(self, resp)

	def login(self):
		Logging.notice("Logging in")
		credentials = self.settings["credentials"][0].split(":", 2)
		credentials[2] = credentials[2].decode("string_escape")
		credentials_enc = json.dumps(credentials, separators=(',',':'))

		self.send_command("connect", credentials, self.logged_in)

	def track_uri(self, id, codec, callback):
		args = [codec, id]
		self.send_command("sp/track_uri", args, callback)

	def metadata_request(self, uris, callback):
		mercury_requests = mercury_pb2.MercuryMultiGetRequest()

		if type(uris) != list:
			uris = [uris]

		for uri in uris:
			uri_type = SpotifyUtil.get_uri_type(uri)
			id = SpotifyUtil.uri2id(uri)

			mercury_request = mercury_pb2.MercuryRequest()
			mercury_request.body = "GET"
			mercury_request.uri = "hm://metadata/"+uri_type+"/"+id

			mercury_requests.request.extend([mercury_request])

		args = [0]

		if len(mercury_requests.request) == 1:
			req = base64.encodestring(mercury_requests.request[0].SerializeToString())
			args.append(req)
		else:
			header = mercury_pb2.MercuryRequest()
			header.body = "GET"
			header.uri = "hm://metadata/"+SpotifyUtil.get_uri_type(uris[0])+"s"
			header.content_type = "vnd.spotify/mercury-mget-request"

			header_str = base64.encodestring(header.SerializeToString())
			req = base64.encodestring(mercury_requests.SerializeToString())
			args.extend([header_str, req])

		self.send_command("sp/hm_b64", args, callback)

	def playlist_request(self, playlist_id, fromnum, num, callback):
		mercury_request = mercury_pb2.MercuryRequest()
		mercury_request.body = "GET"
		mercury_request.uri = "hm://playlist/user/"+self.username+"/playlist/" + playlist_id + "?from=" + str(fromnum) + "&length=" + str(num)
		req = base64.encodestring(mercury_request.SerializeToString())
		args = [0, req]
		self.send_command("sp/hm_b64", args, callback)

	def track_progress(self, lid, ms, randnum, userid, playlist, trackuri, callback):
		args = [lid, "playlist", "clickrow", ms, randnum,
		 "spotify:user:" + `userid` + ":playlist: " +`playlist`,
		 trackuri, "spotify:app:playlist:" + `playlist`, "0.1.0", "com.spotify"]
		self.send_command("sp/track_progress", args, callback)


	def track_event(self, lid, eventcode, secondNum, callback):
		args = [lid, eventcode, secondNum]
		#print args
		self.send_command("sp/track_event", args, callback)

	def track_end(self, lid, XNum, progressnum, uri, userid, playlistid, callback):
		args = [lid, XNum, XNum, 0, 0, 0, 0, progressnum, uri,
		 "spotify:user:" + `userid` + ":playlist:" + `playlistid`, "playlist", "playlist", "clickrow", "clickrow",
		 "spotify:app:playlist:" + `userid` + ":" + `playlistid`, "0.1.0", "com.spotify", XNum]
		self.send_command("sp/track_end", args, callback)


	def user_info_request(self, callback):
		self.send_command("sp/user_info", callback = callback)

	def send_command(self, name, args = [], callback = None):
		msg = {
			"name": name,
			"id": str(self.seq),
			"args": args
		}

		if callback:
			self.cmd_callbacks[self.seq] = callback
		self.seq += 1

		self.send_string(msg)

	def send_string(self, msg):
		msg_enc = json.dumps(msg, separators=(',',':'))
		Logging.debug("sent " + msg_enc)
		self.ws.send(msg_enc)

	def recv_packet(self, msg):
		Logging.debug("recv " + str(msg))
		packet = json.loads(str(msg))
		if "error" in packet:
			self.handle_error(packet)
			return
		elif "message" in packet:
			self.handle_message(packet["message"])
		elif "id" in packet:
			pid = packet["id"]
			if pid in self.cmd_callbacks:
				self.cmd_callbacks[pid](self, packet["result"])
				self.cmd_callbacks.pop(pid)
			else:
				Logging.notice("Unhandled command response with id " + str(pid))

	def work_callback(self, sp, resp):
		Logging.debug("Got ack for message reply")

	def handle_message(self, msg):
		cmd = msg[0]
		if len(msg) > 1:
			payload = msg[1]
		if cmd == "do_work":
			Logging.debug("Got do_work message, payload: "+payload)
			self.send_command("sp/work_done", ["v1"], self.work_callback)

	def handle_error(self, err):
		if len(err) < 2:
			Logging.error("Unknown error "+str(err))

		major = err["error"][0]
		minor = err["error"][1]

		major_err = {
			12: "Track error",
			13: "Hermes error",
			14: "Hermes service error",
		}

		minor_err = {
			1: "failed to send to backend",
			8: "rate limited",
			408: "timeout",
			429: "too many requests",
		}

		if major in major_err:
			major_str = major_err[major]
		else:
			major_str = "unknown (" + str(major) + ")"

		if minor in minor_err:
			minor_str = minor_err[minor]
		else:
			minor_str = "unknown (" + str(minor) + ")"

		if minor == 0:
			Logging.error(major_str)
		else:
			Logging.error(major_str + " - " + minor_str)

	def connect(self):
		if self.settings == None:
			Logging.error("You must authenticate before connecting")
			return False

		Logging.notice("Connecting to "+self.settings["aps"]["ws"][0])
		
		try:
			self.ws = SpotifyClient(self.settings["aps"]["ws"][0])
			self.ws.set_api(self)
			self.ws.connect()
			while not self.ws.terminated:
				continue
		except KeyboardInterrupt:
			self.ws.close()


def track_uri_callback(sp, result):
	print str(result)
	if "type" in result and result["type"] == 3:
		Logging.notice("Track is not available. Skipping.")
		track_end_callback(sp, None)
		return

	if sp.currentLid != "":
		print("LID")
		sp.track_end(sp.currentLid, 0, 97, sp.currentUri, sp.currentUserid, sp.currentPlaylistId, track_end_callback)

	print result
	lid = result["lid"]
	#print "URL: " +result["uri"]
	#print "LID: " + lid
	Logging.notice("Got URL successfully")
	sp.currentLid = lid
	sp.track_event(lid, 3, 0, track_event_callback)

def track_event_callback(sp, result):
	Logging.notice("Track event 'successful'! Calling sp/track_progress." + result.__str__())
	sp.track_progress(sp.currentLid, 500, 97, sp.currentUserid, sp.currentPlaylistId, sp.currentUri, track_progress_callback)

def track_end_callback(sp, result):
	#time.sleep(5)
	Logging.notice("Track ended.")
	sp.currentTrackNum += 1
	uri = sp.currentTracks[sp.currentTrackNum]
	sp.currentUri = uri
	print "Current URI: " + uri
	id = SpotifyUtil.uri2id(uri)
	sp.send_command("sp/echo", ["h"])
	sp.send_command("sp/log", [30, 1, "heartbeat", 77, 77, 2, False])
	sp.track_uri(id, "mp3160", track_uri_callback)


def track_progress_callback(sp, result):
	ms = 500
	if sp.currentMS == 0:
		ms = 15000
	elif sp.currentMS == 1:
		ms = 30000
	elif sp.currentMS == 2:
		ms = 45000
	sp.currentMS += 1
	if sp.currentMS == 2:
		time.sleep(1)
		sp.currentMS = 0
		Logging.notice("Song ended, calling sp/track_event")
		Logging.notice("Current URI: " + sp.currentUri)
		sp.track_event(sp.currentLid, 4, 45000, track_end_callback)
		#It seems track_end is only called AFTER track_uri is called for the new song, so it's irrelevant here.
		#sp.track_end(sp.currentLid, 0, 97, sp.currentUri, sp.currentUserid, sp.currentPlaylistId, track_end_callback)
	else:
		Logging.notice("Song is " + `ms` + "ms in.")
		sp.track_progress(sp.currentLid, ms, 97, sp.currentUserid, sp.currentPlaylistId, sp.currentUri, track_progress_callback)





def multi_track_metadata_callback(sp, result):
	tracks = SpotifyUtil.metadata_resp_to_obj(result)
	for track in tracks:
		print track.name

def track_metadata_callback(sp, result):
	track = SpotifyUtil.metadata_resp_to_obj(result)
	print track.name

def album_metadata_callback(sp, result):
	album = SpotifyUtil.metadata_resp_to_obj(result)
	print album.name+"\n"
	uris = []
	for track in album.disc[0].track:
		uris.append(SpotifyUtil.id2uri("track", SpotifyUtil.gid2id(track.gid)))
		#sp.track_uri(SpotifyUtil.gid2id(track.gid), "mp3160", track_uri_callback)
	sp.metadata_request(uris, multi_track_metadata_callback)

def playlist_callback(sp, result):
	playlist = SpotifyUtil.parse_playlist(result)

	print playlist.attributes.name+"\n"
	uris = []
	for track in playlist.contents.items:
		if SpotifyUtil.get_uri_type(track.uri) != "track":
			continue
		uris.append(track.uri)
	
	sp.metadata_request(uris, track_metadata_callback)

def userdata_callback(sp, result):
	print result["user"]

def login_callback(sp, result):
	#sp.user_info_request(userdata_callback)
	sp.metadata_request("spotify:album:2mduHypWQwgRXMQ9kEFssu", album_metadata_callback)
	#sp.metadata_request("spotify:track:5DRLxox45OZGJycLUhJ4h7", track_metadata_callback)
	#sp.playlist_request("2ITsmcN6qU9NbotiH02Skn", 0, 200, playlist_callback)

sp = SpotifyAPI(login_callback)
sp.auth()
sp.connect()
