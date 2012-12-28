#!/usr/bin/env python

import sys; sys.path.append("..")
import ctypes
from spotify_web.spotify import SpotifyAPI
import pycurl

mpg123 = ctypes.CDLL('libmpg123.so.0')
ao = ctypes.CDLL('libao.so.4')
pycurl.global_init(pycurl.GLOBAL_ALL)
ao.ao_initialize()
mpg123.mpg123_init()
mpg123_new = mpg123.mpg123_new
mpg123_new.restype = ctypes.c_void_p
mh = mpg123_new(ctypes.c_char_p(None), None)
mpg123.mpg123_open_feed(ctypes.c_void_p(mh))

MPG123_NEW_FORMAT = -11
MPG123_DONE = -12
MPG123_OK = 0
MPG123_NEED_MORE = -10

AO_FMT_NATIVE = 4

BITS = 8

class AOSampleFormat(ctypes.Structure):
	_fields_ = [("bits", ctypes.c_int),
				("rate", ctypes.c_int),
				("channels", ctypes.c_int),
				("byte_format", ctypes.c_int),
				("matrix", ctypes.c_char_p)]

aodev = None
count = 0

def play_stream(buf):
	global count
	global aodev

	mpg123.mpg123_feed(ctypes.c_void_p(mh), buf, len(buf))
	done = ctypes.c_int(1)
	offset = ctypes.c_size_t(0)

	channels = ctypes.c_int(0)
	encoding = ctypes.c_int(0)
	rate = ctypes.c_int(0)

	audio = ctypes.c_char_p()

	while done.value > 0:
		err = mpg123.mpg123_decode_frame(ctypes.c_void_p(mh), ctypes.pointer(offset), ctypes.pointer(audio), ctypes.pointer(done))
		if err == MPG123_NEW_FORMAT:
			mpg123.mpg123_getformat(ctypes.c_void_p(mh), ctypes.pointer(rate), ctypes.pointer(channels), ctypes.pointer(encoding))
			fmt = AOSampleFormat()
			fmt.bits = ctypes.c_int(mpg123.mpg123_encsize(encoding)*BITS)
			fmt.rate = rate
			fmt.channels = channels
			fmt.byte_format = AO_FMT_NATIVE
			fmt.matrix = 0
			ao_open_live = ao.ao_open_live
			ao_open_live.restype = ctypes.c_void_p
			aodev = ao_open_live(ao.ao_default_driver_id(), ctypes.pointer(fmt), None)
		elif err == MPG123_OK:
			ao.ao_play(ctypes.c_void_p(aodev), audio, done)
	return len(buf)

def uri_callback(sp, res):
	global aodev
	uri = res['uri']

	curl_obj = pycurl.Curl()
	curl_obj.setopt(pycurl.WRITEFUNCTION, play_stream)
	curl_obj.setopt(pycurl.URL, str(uri))
	curl_obj.perform()
	curl_obj.cleanup()

	sp.disconnect()

	mpg123.mpg123_close(ctypes.c_void_p(mh))
	mpg123.mpg123_delete(ctypes.c_void_p(mh))
	mpg123.mpg123_exit()

	ao.ao_close(ctypes.c_void_p(aodev))
	ao.ao_shutdown()

def login_callback(sp, ok):
	if ok:
		uri = sys.argv[3] if len(sys.argv) > 3 else "spotify:track:6NwbeybX6TDtXlpXvnUOZC"
		track = sp.metadata_request(uri)
		print track.name, track.duration/1000.0, "seconds"
		sp.track_uri(track, uri_callback)
	else:
		print "Login failed"

if len(sys.argv) < 3:
	print "Usage: "+sys.argv[0]+" <username> <password> [album URI]"
else:
	sp = SpotifyAPI(login_callback)
	sp.connect(sys.argv[1], sys.argv[2])
