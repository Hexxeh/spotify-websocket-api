#!/usr/bin/python

from gevent import monkey; monkey.patch_all()
from ws4py.client.geventclient import WebSocketClient
import base64, binascii, json, pprint, re, requests, string, sys, time, gevent

from .proto import mercury_pb2, metadata_pb2
from .proto import playlist4changes_pb2, playlist4content_pb2
from .proto import playlist4issues_pb2, playlist4meta_pb2
from .proto import playlist4ops_pb2

base62 = "0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"

class Logging():
	log_level = 1

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

class WrapAsync():
	def __init__(self, callback, func, *args):
		self.data = None
		self.marker = gevent.event.AsyncResult()

		callback = self.callback if callback == None else [callback, self.callback]
		func(*args, callback=callback)

	def callback(self, *args):
		self.marker.set()
		self.data = args

	def get_data(self):
		self.marker.get()

		if len(self.data) > 0 and type(self.data[0] == SpotifyAPI):
			self.data = self.data[1:]

		return self.data if len(self.data) > 1 else self.data[0]

class SpotifyClient(WebSocketClient):
	def set_api(self, api):
		self.api_object = api

	def opened(self):
		self.api_object.login()

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

class SpotifyAPI():
	def __init__(self, login_callback_func = False):
		self.auth_server = "play.spotify.com"

		self.logged_in_marker = gevent.event.AsyncResult()
		self.username = None
		self.password = None
		self.account_type = None
		self.country = None

		self.settings = None

		self.disconnecting = False
		self.ws = None
		self.seq = 0
		self.cmd_callbacks = {}
		self.login_callback = login_callback_func

	def auth(self, username, password):
		if self.settings != None:
			Logging.warn("You must only authenticate once per API object")
			return False

		headers = {
			"User-Agent": "spotify-websocket-api (Chrome/13.37 compatible-ish)",
		}

		session = requests.session()

		secret_payload = {
			"album": "http://open.spotify.com/album/2mCuMNdJkoyiXFhsQCLLqw",
			"song": "http://open.spotify.com/track/6JEK0CvvjDjjMUBFoXShNZ",
		}

		resp = session.get("https://"+self.auth_server+"/redirect/facebook/notification.php", params=secret_payload, headers = headers)
		data = resp.text

		rx = re.compile("<form><input id=\"secret\" type=\"hidden\" value=\"(.*)\" /></form>")
		r = rx.search(data)

		if not r or len(r.groups()) < 1:
			Logging.error("There was a problem authenticating, no auth secret found")
			self.do_login_callback(False)
			return False
		secret = r.groups()[0]

		login_payload = {
			"type": "sp",
			"username": username,
			"password": password,
			"secret": secret,
		}
		resp = session.post("https://"+self.auth_server+"/xhr/json/auth.php", data=login_payload, headers = headers)
		resp_json = resp.json()

		if resp_json["status"] != "OK":
			Logging.error("There was a problem authenticating, authentication failed")
			self.do_login_callback(False)
			return False

		self.settings = resp.json()["config"]

	def auth_from_json(self, json):
		self.settings = json

	def populate_userdata_callback(self, sp, resp):
		self.username = resp["user"]
		self.country = resp["country"]
		self.account_type = resp["catalogue"]
		if self.login_callback != False:
			self.do_login_callback(True)
		else:
			self.logged_in_marker.set()

	def logged_in(self, sp, resp):
		self.user_info_request(self.populate_userdata_callback)

	def login(self):
		Logging.notice("Logging in")
		credentials = self.settings["credentials"][0].split(":", 2)
		credentials[2] = credentials[2].decode("string_escape")
		credentials_enc = json.dumps(credentials, separators=(',',':'))

		self.send_command("connect", credentials, self.logged_in)

	def do_login_callback(self, result):
		if self.login_callback != False:
			gevent.spawn(self.login_callback, self, result)
		else:
			self.logged_in_marker.set()

	def track_uri(self, id, callback = False):
		args = ["mp3160", id]
		if callback == False:
			data = WrapAsync(None, self.send_command, "sp/track_uri", args).get_data()
			return data
		else:
			self.send_command("sp/track_uri", args, callback)

	def parse_metadata(self, resp):
		header = mercury_pb2.MercuryReply()
		header.ParseFromString(base64.decodestring(resp[0]))

		if header.status_message == "vnd.spotify/mercury-mget-reply":
			mget_reply = mercury_pb2.MercuryMultiGetReply()
			mget_reply.ParseFromString(base64.decodestring(resp[1]))
			items = []
			for reply in mget_reply.reply:
				item = self.parse_metadata_item(reply.content_type, reply.body)
				items.append(item)
			return items
		else:
			return self.parse_metadata_item(header.status_message, base64.decodestring(resp[1]))

	def parse_metadata_item(self, content_type, body):
		if content_type == "vnd.spotify/metadata-album":
			obj = metadata_pb2.Album()
		elif content_type == "vnd.spotify/metadata-track":
			obj = metadata_pb2.Track()
		else:
			Logging.error("Unrecognised metadata type " + content_type)
			return False

		obj.ParseFromString(body)

		if content_type == "vnd.spotify/metadata-track":
			obj = self.recurse_alternatives(obj)

		return obj

	def parse_playlist(self, resp):
		obj = playlist4changes_pb2.ListDump()
		res = base64.decodestring(resp[1])
		obj.ParseFromString(res)
		return obj

	def is_track_available(self, track):
		allowed_countries = []
		forbidden_countries = []
		allowed = False
		forbidden = False

		for restriction in track.restriction:
			allowed_str = restriction.countries_allowed
			allowed_countries += [allowed_str[i:i+2] for i in range(0, len(allowed_str), 2)]

			forbidden_str = restriction.countries_forbidden
			forbidden_countries += [forbidden_str[i:i+2] for i in range(0, len(forbidden_str), 2)]

			allowed = len(allowed_countries) == 0 or self.country in allowed_countries
			forbidden = self.country in forbidden_countries

			if allowed == True and forbidden == False:
				break

		return allowed == True and forbidden == False

	def recurse_alternatives(self, track):
		if self.is_track_available(track):
			return track
		else:
			for alternative in track.alternative:
				found = self.recurse_alternatives(self.metadata_request(SpotifyUtil.gid2uri("track", alternative.gid)))
				if found != False:
					return found
			return False

	def generate_multiget_args(self, metadata_type, requests):
		args = [0]

		if len(requests.request) == 1:
			req = base64.encodestring(requests.request[0].SerializeToString())
			args.append(req)
		else:
			header = mercury_pb2.MercuryRequest()
			header.body = "GET"
			header.uri = "hm://metadata/"+metadata_type+"s"
			header.content_type = "vnd.spotify/mercury-mget-request"

			header_str = base64.encodestring(header.SerializeToString())
			req = base64.encodestring(requests.SerializeToString())
			args.extend([header_str, req])

		return args

	def metadata_request(self, uris, callback = False):
		mercury_requests = mercury_pb2.MercuryMultiGetRequest()

		if type(uris) != list:
			uris = [uris]

		for uri in uris:
			uri_type = SpotifyUtil.get_uri_type(uri)
			if uri_type == "local":
				Logging.warn("Track with URI "+uri+" is a local track, we can't request metadata, skipping")
				continue

			id = SpotifyUtil.uri2id(uri)

			mercury_request = mercury_pb2.MercuryRequest()
			mercury_request.body = "GET"
			mercury_request.uri = "hm://metadata/"+uri_type+"/"+id

			mercury_requests.request.extend([mercury_request])

		args = self.generate_multiget_args(SpotifyUtil.get_uri_type(uris[0]), mercury_requests)

		if callback == False:
			data = WrapAsync(self.metadata_response, self.send_command, "sp/hm_b64", args).get_data()
			return data
		else:
			callback = [callback] if type(callback) != list else callback
			self.send_command("sp/hm_b64", args, [self.metadata_response]+callback)

	def metadata_response(self, sp, resp, callback_data):
		obj = self.parse_metadata(resp)
		if len(callback_data) > 1:
			callback_data[0](self, obj, callback_data[1:])
		else:
			callback_data[0](self, obj)

	def playlists_request(self, user, fromnum = 0, num = 100, callback = False):
		if num > 100:
			Logging.error("You may only request up to 100 playlists at once")
			return False

		mercury_request = mercury_pb2.MercuryRequest()
		mercury_request.body = "GET"
		mercury_request.uri = "hm://playlist/user/"+user+"/rootlist?from=" + str(fromnum) + "&length=" + str(num)
		req = base64.encodestring(mercury_request.SerializeToString())

		args = [0, req]

		if callback == False:
			data = WrapAsync(self.playlist_response, self.send_command, "sp/hm_b64", args).get_data()
			return data
		else:
			callback = [callback] if type(callback) != list else callback
			self.send_command("sp/hm_b64", args, [self.playlist_response]+callback)


	def playlist_request(self, uris, fromnum = 0, num = 100, callback = False):
		if num > 100:
			Logging.error("You may only request up to 100 tracks at once")
			return False

		mercury_requests = mercury_pb2.MercuryMultiGetRequest()

		if type(uris) != list:
			uris = [uris]

		for uri in uris:
			playlist = uri.split(":")
			mercury_request = mercury_pb2.MercuryRequest()
			mercury_request.body = "GET"
			mercury_request.uri = "hm://playlist/user/"+playlist[2]+"/playlist/" + playlist[4] + "?from=" + str(fromnum) + "&length=" + str(num)
			mercury_requests.request.extend([mercury_request])

		args = self.generate_multiget_args(SpotifyUtil.get_uri_type(uris[0]), mercury_requests)
		if callback == False:
			data = WrapAsync(self.playlist_response, self.send_command, "sp/hm_b64", args).get_data()
			return data
		else:
			callback = [callback] if type(callback) != list else callback
			self.send_command("sp/hm_b64", args, [self.playlist_response]+callback)

	def playlist_response(self, sp, resp, callback_data):
		obj = self.parse_playlist(resp)
		if len(callback_data) > 1:
			callback_data[0](self, obj, callback_data[1:])
		else:
			callback_data[0](self, obj)

	def playlist_op_track(self, playlist_uri, track_uri, op, callback = None):
		playlist = playlist_uri.split(":")
		user = playlist[2]
		if playlist[3] == "starred":
			playlist_id = "starred"
		else:
			playlist_id = "playlist/"+playlist[4]

		mercury_request = mercury_pb2.MercuryRequest()
		mercury_request.body = op
		mercury_request.uri = "hm://playlist/user/"+user+"/" + playlist_id + "?syncpublished=1"
		print mercury_request.__str__()
		req = base64.encodestring(mercury_request.SerializeToString())
		args = [0, req, base64.encodestring(track_uri)]
		self.send_command("sp/hm_b64", args, callback)

	def playlist_add_track(self, playlist_uri, track_uri, callback = None):
		self.playlist_op_track(playlist_uri, track_uri, "ADD", callback)

	def playlist_remove_track(self, playlist_uri, track_uri, callback = None):
		self.playlist_op_track(playlist_uri, track_uri, "REMOVE", callback)

	def set_starred(self, track_uri, starred = True, callback = None):
		if starred:
			self.playlist_add_track("spotify:user:"+self.username+":starred", track_uri, callback)
		else:
			self.playlist_remove_track("spotify:user:"+self.username+":starred", track_uri, callback)

	def track_progress(self, lid, ms, randnum, userid, playlist, trackuri, callback):
		args = [lid, "playlist", "clickrow", ms, randnum,
		 "spotify:user:" + userid + ":playlist: " + playlist,
		 trackuri, "spotify:app:playlist:" + playlist, "0.1.0", "com.spotify"]
		self.send_command("sp/track_progress", args, callback)


	def track_event(self, lid, eventcode, secondNum, callback):
		args = [lid, eventcode, secondNum]
		self.send_command("sp/track_event", args, callback)

	def track_end(self, lid, XNum, progressnum, uri, userid, playlistid, callback):
		args = [lid, XNum, XNum, 0, 0, 0, 0, progressnum, uri,
		 "spotify:user:" + userid + ":playlist:" + playlistid, "playlist", "playlist", "clickrow", "clickrow",
         "spotify:app:playlist:" + userid + ":" + playlistid, "0.1.0", "com.spotify", XNum]
		self.send_command("sp/track_end", args, callback)

	def search_request(self, query, callback = None):
		args = [query]
		self.send_command("sp/search", args, callback = callback)

	def user_info_request(self, callback = None):
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

	def event_handler(self):
		while self.disconnecting == False:
			m = self.ws.receive()
			if m is not None:
				self.recv_packet(str(m))
			else:
				break

	def connect(self, username, password):
		if self.settings == None:
			 if self.auth(username, password) == False:
			 	return False

		Logging.notice("Connecting to "+self.settings["aps"]["ws"][0])
		
		try:
			self.ws = SpotifyClient(self.settings["aps"]["ws"][0])
			self.ws.set_api(self)
			self.ws.connect()
			self.greenlets = [
				gevent.spawn(self.event_handler)
			]
			if self.login_callback != False:
				gevent.joinall(self.greenlets)
			else:
				self.logged_in_marker.get()
		except:
			self.disconnect()

	def block(self):
		gevent.joinall(self.greenlets)

	def disconnect(self):
		self.disconnecting = True

