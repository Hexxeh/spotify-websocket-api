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
	def metadata_resp_to_obj(metadata_type, resp):
		if metadata_type == "album":
			obj = metadata_pb2.Album()
		elif metadata_type == "track":
			obj = metadata_pb2.Track()
		elif metadata_type == "artist":
			obj = metadata_pb2.Artist()
		else:
			Logging.error("invalid metadata_type given")
			return False

		obj.ParseFromString(base64.decodestring(resp[1]))
		return obj

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

	def metadata_request(self, metadata_type, id, callback):
		mercury_request = mercury_pb2.MercuryRequest()
		mercury_request.body = "GET"
		mercury_request.uri = "hm://metadata/"+metadata_type+"/"+id
		req = base64.encodestring(mercury_request.SerializeToString())
		args = [0, req]
		self.send_command("sp/hm_b64", args, callback)

	def playlist_request(self, playlist_id, fromnum, num, callback):
		mercury_request = mercury_pb2.MercuryRequest()
		mercury_request.body = "GET"
		mercury_request.uri = "hm://playlist/user/geel9/playlist/" + playlist_id + "?from=" + `fromnum` + "&length=" + `num`
		req = base64.encodestring(mercury_request.SerializeToString())
		args = [0, req]
		self.send_command("sp/hm_b64", args, callback)

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

	def handle_message(self, msg):
		cmd = msg[0]
		if len(msg) > 1:
			payload = msg[1]
		if cmd == "do_work":
			Logging.debug("Got do_work message, payload: "+payload)
			self.send_command("sp/work_done", ["v2"])

	def handle_error(self, err):
		Logging.error(str(err))

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
	print "URL: "+result["uri"]

def track_metadata_callback(sp, result):
	print result
	track = SpotifyUtil.metadata_resp_to_obj("track", result)
	print track.name

def album_metadata_callback(sp, result):
	album = SpotifyUtil.metadata_resp_to_obj("album", result)
	print album.name+"\n"
	for track in album.disc[0].track:
		sp.metadata_request("track", SpotifyUtil.gid2id(track.gid), track_metadata_callback)
		#sp.track_uri(SpotifyUtil.gid2id(track.gid), "mp3160", track_uri_callback)

def playlist_callback(sp, result):
	obj = playlist4changes_pb2.ListDump()
	res = base64.decodestring(result[1])
	obj.ParseFromString(res)
	print obj.attributes.name+"\n"
	for track in obj.contents.items:
		if SpotifyUtil.get_uri_type(track.uri) != "track":
			continue
		print track.uri
		sp.metadata_request("track", SpotifyUtil.uri2id(track.uri), track_metadata_callback)

def userdata_callback(sp, result):
	print result["user"]

def login_callback(sp, result):
	#sp.user_info_request(userdata_callback)
	#sp.metadata_request("album", SpotifyUtil.uri2id("spotify:album:3OmHoatMS34vM7ZKb4WCY3"), album_metadata_callback)
	sp.playlist_request("2ITsmcN6qU9NbotiH02Skn", 0, 200, playlist_callback)

sp = SpotifyAPI(login_callback)
sp.auth()
sp.connect()
