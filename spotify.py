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
		Logging.debug("Connection closed, code %d reason %s" % (code, reason))

	def received_message(self, m):
		self.api_object.recv_packet(m)

class SpotifyUtil():
	@staticmethod
	def gid2id(gid):
		return binascii.hexlify(gid).rjust(32, "0")

	@staticmethod
	def id2uri(uritype, v):
		res = []
		v = int(v, 16)
		while v > 0:
		    res = [v % 62] + res
		    v = v / 62
		id = ''.join([base62[i] for i in res])
		return ("spotify:"+uritype+":"+id).rjust(22, "0")

	@staticmethod
	def uri2id(uri):
		parts = uri.split(":")
		if len(parts) > 3 and parts[3] == "playlist":
			s = parts[4]
		else:
			s = parts[2]

		v = 0
		for c in s:
		    v = v * 62 + base62.index(c)
		return hex(v)[2:-1].rjust(32, "0")

	@staticmethod
	def gid2uri(uritype, gid):
		id = SpotifyUtil.gid2id(gid)
		uri = SpotifyUtil.id2uri(uritype, id)
		return uri

	@staticmethod
	def get_uri_type(uri):	
		return uri.split(":")[1]

	@staticmethod
	def parse_metadata(resp):
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
		self.login_callback(self)

	def logged_in(self, sp, resp):
		self.user_info_request(self.populate_userdata_callback)

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

		self.send_command("sp/hm_b64", args, [self.metadata_response, callback])

	def metadata_response(self, sp, resp, callback_data):
		obj = SpotifyUtil.parse_metadata(resp)
		callback_data[0](self, obj)

	def playlist_request(self, uri, fromnum, num, callback):
		if num > 100:
			Logging.error("You may only request up to 100 tracks at once")
			return False

		playlist = uri.split(":")
		mercury_request = mercury_pb2.MercuryRequest()
		mercury_request.body = "GET"
		mercury_request.uri = "hm://playlist/user/"+playlist[2]+"/playlist/" + playlist[4] + "?from=" + str(fromnum) + "&length=" + str(num)
		print mercury_request.uri
		req = base64.encodestring(mercury_request.SerializeToString())
		args = [0, req]
		self.send_command("sp/hm_b64", args, [self.playlist_response, callback])

	def playlist_response(self, sp, resp, callback_data):
		obj = SpotifyUtil.parse_playlist(resp)
		callback_data[0](self, obj)

	def track_progress(self, lid, ms, randnum, userid, playlist, trackuri, callback):
		args = [lid, "playlist", "clickrow", ms, randnum,
		 "spotify:user:" + userid + ":playlist: " + playlist,
		 trackuri, "spotify:app:playlist:" + playlist, "0.1.0", "com.spotify"]
		self.send_command("sp/track_progress", args, callback)


	def track_event(self, lid, eventcode, secondNum, callback):
		args = [lid, eventcode, secondNum]
		#print args
		self.send_command("sp/track_event", args, callback)

	def track_end(self, lid, XNum, progressnum, uri, userid, playlistid, callback):
		args = [lid, XNum, XNum, 0, 0, 0, 0, progressnum, uri,
		 "spotify:user:" + userid + ":playlist:" + playlistid, "playlist", "playlist", "clickrow", "clickrow",
         "spotify:app:playlist:" + userid + ":" + playlistid, "0.1.0", "com.spotify", XNum]
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
				callback = self.cmd_callbacks[pid]

				if type(callback) == list:
					callback[0](self, packet["result"], callback[1:])
				else:
					callback(self, packet["result"])

				self.cmd_callbacks.pop(pid)
			else:
				Logging.debug("Unhandled command response with id " + str(pid))

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
			self.auth()

		Logging.notice("Connecting to "+self.settings["aps"]["ws"][0])
		
		try:
			self.ws = SpotifyClient(self.settings["aps"]["ws"][0])
			self.ws.set_api(self)
			self.ws.connect()
			while not self.ws.terminated:
				continue
		except KeyboardInterrupt:
			self.ws.close()

	def disconnect(self):
		self.ws.close()

