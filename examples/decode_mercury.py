#!/usr/bin/env python
import sys
sys.path.append("..")
import base64
from spotify_web.proto import mercury_pb2, metadata_pb2, playlist4ops_pb2, playlist4service_pb2, playlist4changes_pb2


msg_types = {
    "request": mercury_pb2.MercuryRequest,
    "reply": mercury_pb2.MercuryReply,
    "mget_request": mercury_pb2.MercuryMultiGetRequest,
    "mget_reply": mercury_pb2.MercuryMultiGetReply,
    "track": metadata_pb2.Track,
    "album": metadata_pb2.Album,
    "createlistreply": playlist4service_pb2.CreateListReply,
    "listdump": playlist4changes_pb2.ListDump,
    "oplist": playlist4ops_pb2.OpList
}

msg = sys.argv[2]

if sys.argv[1] == "op":
    request = msg_types["request"]()
    request.ParseFromString(base64.decodestring(msg))
    print request.__str__()
    op = playlist4ops_pb2.Op()
    op.ParseFromString(str(request.uri))
    obj = op
else:
    ctor = msg_types[sys.argv[1]]
    obj = ctor()
    obj.ParseFromString(base64.decodestring(msg))
print obj.__str__()
