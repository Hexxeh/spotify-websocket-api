import sys, base64

sys.path.append("proto")

import mercury_pb2, metadata_pb2

msg = sys.argv[1]
mercury_reply = mercury_pb2.MercuryRequest()
mercury_reply.ParseFromString(base64.decodestring(msg))

print mercury_reply.__str__()
