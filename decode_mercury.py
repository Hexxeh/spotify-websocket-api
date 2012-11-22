#!/usr/bin/python
import sys, base64

sys.path.append("proto")

import mercury_pb2, metadata_pb2

msg_types = {
	"request": mercury_pb2.MercuryRequest,
	"reply": mercury_pb2.MercuryReply,
	"mget_request": mercury_pb2.MercuryMultiGetRequest,
	"mget_reply": mercury_pb2.MercuryMultiGetReply
}

msg = sys.argv[2]
ctor = msg_types[sys.argv[1]]

obj = ctor()
obj.ParseFromString(base64.decodestring(msg))
print obj.__str__()
