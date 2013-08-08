#!/usr/bin/python

import base64, json, re, sys

sys.path.append("..")
from spotify_web.proto import mercury_pb2, metadata_pb2, playlist4ops_pb2, playlist4service_pb2, playlist4changes_pb2

def decode_hermes(prefix, json_obj):
	if prefix == ">>":
		ctor = mercury_pb2.MercuryRequest
		msg = json_obj["args"][1]
	else:
		ctor = mercury_pb2.MercuryReply
		msg = json_obj["result"][0]

	obj = ctor()
	obj.ParseFromString(base64.decodestring(msg))
	return obj.__str__()

undecoded = 0
undecoded_names = set()

with open(sys.argv[1], "r") as f:
	for line in f.readlines():
		prefix = line[:2]
		if prefix != ">>" and prefix != "<<":
			continue

		rx = re.compile("(\{.*\})")
		r = rx.search(line)

		if len(r.groups()) < 1:
			break
		
		obj_str = r.groups()[0]
		obj = json.loads(obj_str)

		if "id" not in obj or "name" not in obj:
			continue

		#if int(obj["id"]) > 20:
			#break

		cmd = obj["name"]
		cmd = cmd[3:] if "sp/" in cmd else cmd
		if cmd == "hm_b64":
			decode_hermes(prefix, obj)
		elif cmd == "track_uri":
			print obj
		elif cmd == "connect":
			continue
		elif cmd == "echo" or cmd == "log":
			continue
		elif cmd == "log_ce" or cmd == "log_view":
			continue
		else:
			undecoded += 1
			undecoded_names.add(cmd)

print "%d messages were not decoded" % undecoded
print ', '.join(undecoded_names)