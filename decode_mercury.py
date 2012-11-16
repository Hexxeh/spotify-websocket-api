import sys, base64

sys.path.append("proto")

import mercury_proto

msg = "CjRobTovL21ldGFkYXRhL2FsYnVtL2ZhODkyY2E5Yzk5NjQ5MjRiNmZkZTYyNTAxMzBjZmVjGgNHRVQ="
mercury_reply = mercury_proto.MercuryRequest()
mercury_reply.ParseFromString(base64.decodestring(msg))

print mercury_reply.__str__()
