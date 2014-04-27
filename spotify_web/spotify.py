#!/usr/bin/python
import re
import json
import operator
import binascii
import base64
from ssl import SSLError
from threading import Thread, Event, Lock

import requests
from ws4py.client.threadedclient import WebSocketClient

from .proto import mercury_pb2, metadata_pb2, playlist4changes_pb2,\
    playlist4ops_pb2, playlist4service_pb2, toplist_pb2

# from .proto import playlist4meta_pb2, playlist4issues_pb2,
# playlist4content_pb2


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
    timeout = 10

    def __init__(self, callback, func, *args):
        self.marker = Event()

        if callback is None:
            callback = self.callback
        elif type(callback) == list:
            callback = callback+[self.callback]
        else:
            callback = [callback, self.callback]

        self.data = False
        func(*args, callback=callback)

    def callback(self, *args):
        self.data = args
        self.marker.set()

    def get_data(self):
        try:
            self.marker.wait(timeout=self.timeout)

            if len(self.data) > 0 and type(self.data[0] == SpotifyAPI):
                self.data = self.data[1:]

            return self.data if len(self.data) > 1 else self.data[0]
        except:
            return False


class SpotifyClient(WebSocketClient):
    def set_api(self, api):
        self.api_object = api

    def opened(self):
        self.api_object.login()

    def received_message(self, m):
        self.api_object.recv_packet(m)

    def closed(self, code, message):
        self.api_object.shutdown()


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
            v /= 62
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
        uri_parts = uri.split(":")

        if len(uri_parts) >= 3 and uri_parts[1] == "local":
            return "local"
        elif len(uri_parts) >= 5:
            return uri_parts[3]
        elif len(uri_parts) >= 4 and uri_parts[3] == "starred":
            return "playlist"
        elif len(uri_parts) >= 3:
            return uri_parts[1]
        else:
            return False

    @staticmethod
    def is_local(uri):
        return SpotifyUtil.get_uri_type(uri) == "local"


class SpotifyAPI():
    def __init__(self, login_callback_func=False):
        self.auth_server = "play.spotify.com"

        self.logged_in_marker = Event()
        self.heartbeat_marker = Event()
        self.username = None
        self.password = None
        self.account_type = None
        self.country = None

        self.settings = None

        self.disconnecting = False
        self.ws = None
        self.ws_lock = Lock()
        self.seq = 0
        self.cmd_callbacks = {}
        self.login_callback = login_callback_func
        self.is_logged_in = False

    def auth(self, username, password):
        if self.settings is not None:
            Logging.warn("You must only authenticate once per API object")
            return False

        headers = {
            #"User-Agent": "node-spotify-web in python (Chrome/13.37 compatible-ish)",
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_9_1) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/31.0.1650.63 Safari/537.36"
        }

        session = requests.session()

        resp = session.get("https://" + self.auth_server, headers=headers)
        data = resp.text

        #csrftoken
        rx = re.compile("\"csrftoken\":\"(.*?)\"")
        r = rx.search(data)

        if not r or len(r.groups()) < 1:
            Logging.error("There was a problem authenticating, no auth secret found")
            self.do_login_callback(False)
            return False
        secret = r.groups()[0]

        #trackingID
        rx = re.compile("\"trackingId\":\"(.*?)\"")
        r = rx.search(data)

        if not r or len(r.groups()) < 1:
            Logging.error("There was a problem authenticating, no auth trackingId found")
            self.do_login_callback(False)
            return False
        trackingId = r.groups()[0]

        #referrer
        rx = re.compile("\"referrer\":\"(.*?)\"")
        r = rx.search(data)

        if not r or len(r.groups()) < 1:
            Logging.error("There was a problem authenticating, no auth referrer found")
            self.do_login_callback(False)
            return False
        referrer = r.groups()[0]

        #landingURL
        rx = re.compile("\"landingURL\":\"(.*?)\"")
        r = rx.search(data)

        if not r or len(r.groups()) < 1:
            Logging.error("There was a problem authenticating, no auth landingURL found")
            self.do_login_callback(False)
            return False
        landingURL = r.groups()[0]

        login_payload = {
            "type": "sp",
            "username": username,
            "password": password,
            "secret": secret,
            "trackingId":trackingId,
            "referrer": referrer,
            "landingURL": landingURL,
            "cf":"",
        }

        Logging.notice(str(login_payload))
        
        resp = session.post("https://" + self.auth_server + "/xhr/json/auth.php", data=login_payload, headers=headers)
        resp_json = resp.json()

        if resp_json["status"] != "OK":
            Logging.error("There was a problem authenticating, authentication failed")
            self.do_login_callback(False)
            return False

        self.settings = resp.json()["config"]

        #Get wss settings
        resolver_payload = {
            "client": "24:0:0:" + str(self.settings["version"])
        }

        resp = session.get('http://' + self.settings["aps"]["resolver"]["hostname"], params=resolver_payload, headers=headers)

        resp_json = resp.json()
        wss_hostname = resp_json["ap_list"][0].split(":")[0]

        self.settings["wss"] = "wss://" + wss_hostname + "/"

        return True

    def populate_userdata_callback(self, sp, resp):
        
        # Send screen size
        self.send_command("sp/log", [41, 1, 0, 0, 0, 0], None)
        
        self.username = resp["user"]
        self.country = resp["country"]
        self.account_type = resp["catalogue"]

        # If you're thinking about changing this: don't.
        # I don't want to play cat and mouse with Spotify.
        # I just want an open-library that works for paying
        # users.
        magic = base64.b64encode(resp["catalogue"]) == "cHJlbWl1bQ=="
        self.is_logged_in = True if magic else False

        if not magic:
            Logging.error("Please upgrade to Premium")
            self.disconnect()
        else:
            heartbeat_thread = Thread(target=self.heartbeat_handler)
            heartbeat_thread.daemon = True
            heartbeat_thread.start()

        if self.login_callback:
            self.do_login_callback(self.is_logged_in)
        else:
            self.logged_in_marker.set()

    def logged_in(self, sp, resp):
        self.user_info_request(self.populate_userdata_callback)

    def login(self):
        Logging.notice("Logging in")
        credentials = self.settings["credentials"][0].split(":", 2)
        credentials[2] = credentials[2].decode("string_escape")
        # credentials_enc = json.dumps(credentials, separators=(',',':'))

        self.send_command("connect", credentials, self.logged_in)

    def do_login_callback(self, result):
        if self.login_callback:
            Thread(target=self.login_callback, args=(self, result)).start()
        else:
            self.logged_in_marker.set()

    def track_uri(self, track, callback=False):
        track = self.recurse_alternatives(track)
        if not track:
            return False
        args = ["mp3160", SpotifyUtil.gid2id(track.gid)]
        return self.wrap_request("sp/track_uri", args, callback)

    def parse_metadata(self, sp, resp, callback_data):
        header = mercury_pb2.MercuryReply()
        header.ParseFromString(base64.decodestring(resp[0]))

        if header.status_message == "vnd.spotify/mercury-mget-reply":
            if len(resp) < 2:
                ret = False

            mget_reply = mercury_pb2.MercuryMultiGetReply()
            mget_reply.ParseFromString(base64.decodestring(resp[1]))
            items = []
            for reply in mget_reply.reply:
                if reply.status_code != 200:
                    continue

                item = self.parse_metadata_item(reply.content_type, reply.body)
                items.append(item)
            ret = items
        else:
            ret = self.parse_metadata_item(header.status_message, base64.decodestring(resp[1]))

        self.chain_callback(sp, ret, callback_data)

    def parse_metadata_item(self, content_type, body):
        if content_type == "vnd.spotify/metadata-album":
            obj = metadata_pb2.Album()
        elif content_type == "vnd.spotify/metadata-artist":
            obj = metadata_pb2.Artist()
        elif content_type == "vnd.spotify/metadata-track":
            obj = metadata_pb2.Track()
        else:
            Logging.error("Unrecognised metadata type " + content_type)
            return False

        obj.ParseFromString(body)

        return obj

    def parse_toplist(self, sp, resp, callback_data):
        obj = toplist_pb2.Toplist()
        res = base64.decodestring(resp[1])
        obj.ParseFromString(res)
        self.chain_callback(sp, obj, callback_data)

    def parse_playlist(self, sp, resp, callback_data):
        obj = playlist4changes_pb2.ListDump()
        try:
            res = base64.decodestring(resp[1])
            obj.ParseFromString(res)
        except:
            obj = False

        self.chain_callback(sp, obj, callback_data)

    def chain_callback(self, sp, data, callback_data):
        if len(callback_data) > 1:
            callback_data[0](self, data, callback_data[1:])
        elif len(callback_data) == 1:
            callback_data[0](self, data)

    def is_track_available(self, track, country):
        allowed_countries = []
        forbidden_countries = []
        available = False

        for restriction in track.restriction:
            allowed_str = restriction.countries_allowed
            allowed_countries += [allowed_str[i:i+2] for i in range(0, len(allowed_str), 2)]

            forbidden_str = restriction.countries_forbidden
            forbidden_countries += [forbidden_str[i:i+2] for i in range(0, len(forbidden_str), 2)]

            allowed = not restriction.HasField("countries_allowed") or country in allowed_countries
            forbidden = self.country in forbidden_countries and len(forbidden_countries) > 0

            if country in allowed_countries and country in forbidden_countries:
                allowed = True
                forbidden = False

            # guessing at names here, corrections welcome
            account_type_map = {
                "premium": 1,
                "unlimited": 1,
                "free": 0
            }

            applicable = account_type_map[self.account_type] in restriction.catalogue

            # enable this to help debug restriction issues
            if False:
                print restriction
                print allowed_countries
                print forbidden_countries
                print "allowed: "+str(allowed)
                print "forbidden: "+str(forbidden)
                print "applicable: "+str(applicable)

            available = True == allowed and False == forbidden and True == applicable
            if available:
                break

        if available:
            Logging.notice(SpotifyUtil.gid2uri("track", track.gid) + " is available!")
        else:
            Logging.notice(SpotifyUtil.gid2uri("track", track.gid) + " is NOT available!")

        return available

    def recurse_alternatives(self, track, attempted=None, country=None):
        if not attempted:
            attempted = []
        country = self.country if country is None else country
        if self.is_track_available(track, country):
            return track
        else:
            for alternative in track.alternative:
                if self.is_track_available(alternative, country):
                    return alternative
            return False
            for alternative in track.alternative:
                uri = SpotifyUtil.gid2uri("track", alternative.gid)
                if uri not in attempted:
                    attempted += [uri]
                    subtrack = self.metadata_request(uri)
                    return self.recurse_alternatives(subtrack, attempted)
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

    def wrap_request(self, command, args, callback, int_callback=None, retries=3):
        if not callback:
            for attempt in range(0, retries):
                data = WrapAsync(int_callback, self.send_command, command, args).get_data()
                if data:
                    break
            return data
        else:
            callback = [callback] if type(callback) != list else callback
            if int_callback is not None:
                int_callback = [int_callback] if type(int_callback) != list else int_callback
                callback += int_callback
            self.send_command(command, args, callback)

    def metadata_request(self, uris, callback=False):
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

        return self.wrap_request("sp/hm_b64", args, callback, self.parse_metadata)

    def toplist_request(self, toplist_content_type="track", toplist_type="user", username=None, region="global", callback=False):
        if username is None:
            username = self.username

        mercury_request = mercury_pb2.MercuryRequest()
        mercury_request.body = "GET"
        if toplist_type == "user":
            mercury_request.uri = "hm://toplist/toplist/user/"+username
        elif toplist_type == "region":
            mercury_request.uri = "hm://toplist/toplist/region"
            if region is not None and region != "global":
                mercury_request.uri += "/"+region
        else:
            return False
        mercury_request.uri += "?type="+toplist_content_type

        # playlists don't appear to work?
        if toplist_type == "user" and toplist_content_type == "playlist":
            if username != self.username:
                return False
            mercury_request.uri = "hm://socialgraph/suggestions/topplaylists"

        req = base64.encodestring(mercury_request.SerializeToString())

        args = [0, req]

        return self.wrap_request("sp/hm_b64", args, callback, self.parse_toplist)

    def playlists_request(self, user, fromnum=0, num=100, callback=False):
        if num > 100:
            Logging.error("You may only request up to 100 playlists at once")
            return False

        mercury_request = mercury_pb2.MercuryRequest()
        mercury_request.body = "GET"
        mercury_request.uri = "hm://playlist/user/"+user+"/rootlist?from=" + str(fromnum) + "&length=" + str(num)
        req = base64.encodestring(mercury_request.SerializeToString())

        args = [0, req]

        return self.wrap_request("sp/hm_b64", args, callback, self.parse_playlist)

    def playlist_request(self, uri, fromnum=0, num=100, callback=False):
        # mercury_requests = mercury_pb2.MercuryRequest()

        playlist = uri[8:].replace(":", "/")
        mercury_request = mercury_pb2.MercuryRequest()
        mercury_request.body = "GET"
        mercury_request.uri = "hm://playlist/" + playlist + "?from=" + str(fromnum) + "&length=" + str(num)

        req = base64.encodestring(mercury_request.SerializeToString())
        args = [0, req]

        return self.wrap_request("sp/hm_b64", args, callback, self.parse_playlist)

    def playlist_op_track(self, playlist_uri, track_uri, op, callback=None):
        playlist = playlist_uri.split(":")

        if playlist_uri == "rootlist":
            user = self.username
            playlist_id = "rootlist"
        else:
            user = playlist[2]
            if playlist[3] == "starred":
                playlist_id = "starred"
            else:
                playlist_id = "playlist/"+playlist[4]

        mercury_request = mercury_pb2.MercuryRequest()
        mercury_request.body = op
        mercury_request.uri = "hm://playlist/user/"+user+"/" + playlist_id + "?syncpublished=1"
        req = base64.encodestring(mercury_request.SerializeToString())
        args = [0, req, base64.encodestring(track_uri)]
        return self.wrap_request("sp/hm_b64", args, callback)

    def playlist_add_track(self, playlist_uri, track_uri, callback=False):
        return self.playlist_op_track(playlist_uri, track_uri, "ADD", callback)

    def playlist_remove_track(self, playlist_uri, track_uri, callback=False):
        return self.playlist_op_track(playlist_uri, track_uri, "REMOVE", callback)

    def set_starred(self, track_uri, starred=True, callback=False):
        if starred:
            return self.playlist_add_track("spotify:user:"+self.username+":starred", track_uri, callback)
        else:
            return self.playlist_remove_track("spotify:user:"+self.username+":starred", track_uri, callback)

    def playlist_op(self, op, path, optype="update", name=None, index=None, callback=None):
        mercury_request = mercury_pb2.MercuryRequest()
        mercury_request.body = op
        mercury_request.uri = "hm://" + path

        req = base64.encodestring(mercury_request.SerializeToString())

        op = playlist4ops_pb2.Op()
        if optype == "update":
            op.kind = playlist4ops_pb2.Op.UPDATE_LIST_ATTRIBUTES
            op.update_list_attributes.new_attributes.values.name = name
        elif optype == "remove":
            op.kind = playlist4ops_pb2.Op.REM
            op.rem.fromIndex = index
            op.rem.length = 1

        mercury_request_payload = mercury_pb2.MercuryRequest()
        mercury_request_payload.uri = op.SerializeToString()

        payload = base64.encodestring(mercury_request_payload.SerializeToString())

        args = [0, req, payload]
        return self.wrap_request("sp/hm_b64", args, callback, self.new_playlist_callback)

    def new_playlist(self, name, callback=False):
        return self.playlist_op("PUT", "playlist/user/"+self.username, name=name, callback=callback)

    def rename_playlist(self, playlist_uri, name, callback=False):
        path = "playlist/user/"+self.username+"/playlist/"+playlist_uri.split(":")[4]+"?syncpublished=true"
        return self.playlist_op("MODIFY", path, name=name, callback=callback)

    def remove_playlist(self, playlist_uri, callback=False):
        return self.playlist_op_track("rootlist", playlist_uri, "REMOVE", callback=callback)
        #return self.playlist_op("REMOVE", "playlist/user/"+self.username+"/rootlist?syncpublished=true",
                                #optype="remove", index=index, callback=callback)

    def new_playlist_callback(self, sp, data, callback_data):
        try:
            reply = playlist4service_pb2.CreateListReply()
            reply.ParseFromString(base64.decodestring(data[1]))
        except:
            self.chain_callback(sp, False, callback_data)

        mercury_request = mercury_pb2.MercuryRequest()
        mercury_request.body = "ADD"
        mercury_request.uri = "hm://playlist/user/"+self.username+"/rootlist?add_first=1&syncpublished=1"
        req = base64.encodestring(mercury_request.SerializeToString())
        args = [0, req, base64.encodestring(reply.uri)]

        self.chain_callback(sp, reply.uri, callback_data)
        self.send_command("sp/hm_b64", args)

    def search_request(self, query, query_type="all", max_results=50, offset=0, callback=False):
        if max_results > 50:
            Logging.warn("Maximum of 50 results per request, capping at 50")
            max_results = 50

        search_types = {
            "tracks": 1,
            "albums": 2,
            "artists": 4,
            "playlists": 8

        }

        query_type = [k for k, v in search_types.items()] if query_type == "all" else query_type
        query_type = [query_type] if type(query_type) != list else query_type
        query_type = reduce(operator.or_, [search_types[type_name] for type_name in query_type if type_name in search_types])

        args = [query, query_type, max_results, offset]

        return self.wrap_request("sp/search", args, callback)

    def user_info_request(self, callback=None):
        return self.wrap_request("sp/user_info", [], callback)

    def heartbeat(self):
        self.send_command("sp/echo", "h", callback=False)

    def send_track_end(self, lid, track_uri, ms_played, callback=False):
        ms_played = int(ms_played)
        ms_played_union = ms_played
        n_seeks_forward = 0
        n_seeks_backward = 0
        ms_seeks_forward = 0
        ms_seeks_backward = 0
        ms_latency = 100
        display_track = None
        play_context = "unknown"
        source_start = "unknown"
        source_end = "unknown"
        reason_start = "unknown"
        reason_end = "unknown"
        referrer = "unknown"
        referrer_version = "0.1.0"
        referrer_vendor = "com.spotify"
        max_continuous = ms_played
        args = [lid, ms_played, ms_played_union, n_seeks_forward, n_seeks_backward, ms_seeks_forward, ms_seeks_backward, ms_latency, display_track, play_context, source_start, source_end, reason_start, reason_end, referrer, referrer_version, referrer_vendor, max_continuous]
        return self.wrap_request("sp/track_end", args, callback)

    def send_track_event(self, lid, event, ms_where, callback=False):
        if event == "pause" or event == "stop":
            ev_n = 4
        elif event == "unpause" or "continue" or "play":
            ev_n = 3
        else:
            return False
        return self.wrap_request("sp/track_event", [lid, ev_n, int(ms_where)], callback)

    def send_track_progress(self, lid, ms_played, callback=False):
        source_start = "unknown"
        reason_start = "unknown"
        ms_latency = 100
        play_context = "unknown"
        display_track = ""
        referrer = "unknown"
        referrer_version = "0.1.0"
        referrer_vendor = "com.spotify"
        args = [lid, source_start, reason_start, int(ms_played), int(ms_latency), play_context, display_track, referrer, referrer_version, referrer_vendor]
        return self.wrap_request("sp/track_progress", args, callback)

    def send_command(self, name, args=None, callback=None):
        if not args:
            args = []
        msg = {
            "name": name,
            "id": str(self.seq),
            "args": args
        }

        if callback is not None:
            self.cmd_callbacks[self.seq] = callback
        self.seq += 1

        self.send_string(msg)

    def send_string(self, msg):
        if self.disconnecting:
            return

        msg_enc = json.dumps(msg, separators=(',', ':'))
        Logging.debug("sent " + msg_enc)
        try:
            with self.ws_lock:
                self.ws.send(msg_enc)
        except SSLError:
            Logging.notice("SSL error, attempting to continue")

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

                if not callback:
                    Logging.debug("No callback was requested for command " + str(pid) + ", ignoring")
                elif type(callback) == list:
                    if len(callback) > 1:
                        callback[0](self, packet["result"], callback[1:])
                    else:
                        callback[0](self, packet["result"])
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
        if cmd == "ping_flash2":
            if len(msg[1]) >= 20:
                key = [[7, 203], [15, 15], [1, 96], [19, 93], [3, 165], [14, 130], [12, 16], [4, 6], [6, 225], [13, 37]]
                input = [ int(x) for x in msg[1].split(" ") ]
                pong = u' ' .join([unicode((input[i[0]] ^ i[1])) for i in key ])
                Logging.debug("Sending pong %s" % pong)
                self.send_command("sp/pong_flash2", [pong,], None)
        if cmd == "login_complete":
            Logging.debug("Login Complete")
	    self.user_info_request(self.populate_userdata_callback)
    def handle_error(self, err):
        if len(err) < 2:
            Logging.error("Unknown error "+str(err))

        major = err["error"][0]
        minor = err["error"][1]

        major_err = {
            8: "Rate request error",
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

    def heartbeat_handler(self):
        while not self.disconnecting:
            self.heartbeat()
            self.heartbeat_marker.wait(timeout=18)

    def connect(self, username, password, timeout=10):
        if self.settings is None:
            if not self.auth(username, password):
                return False
            self.username = username
            self.password = password

        Logging.notice("Connecting to "+self.settings["wss"])
        
        try:
            self.ws = SpotifyClient(self.settings["wss"])
            self.ws.set_api(self)
            self.ws.daemon = True
            self.ws.connect()
            if not self.login_callback:
                try:
                    self.logged_in_marker.wait(timeout=timeout)
                    return self.is_logged_in
                except:
                    return False
        except:
            self.disconnect()
            return False

    def set_log_level(self, level):
        Logging.log_level = level

    def shutdown(self):
        self.disconnecting = True
        self.heartbeat_marker.set()

    def disconnect(self):
        if self.ws is not None:
            self.ws.close()
