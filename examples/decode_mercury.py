#!/usr/bin/python
import sys; sys.path.append("..")
import base64
from spotify_web.proto import mercury_pb2, metadata_pb2

msg_types = {
	"request": mercury_pb2.MercuryRequest,
	"reply": mercury_pb2.MercuryReply,
	"mget_request": mercury_pb2.MercuryMultiGetRequest,
	"mget_reply": mercury_pb2.MercuryMultiGetReply,
	"track": metadata_pb2.Track,
	"album": metadata_pb2.Album
}

msg = sys.argv[2]
ctor = msg_types[sys.argv[1]]

obj = ctor()
obj.ParseFromString(base64.decodestring(msg))
print obj.__str__()
