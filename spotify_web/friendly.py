from functools import partial
from lxml import etree
from threading import Thread
from Queue import Queue

from .spotify import SpotifyAPI, SpotifyUtil
# from spotify_web.proto import mercury_pb2, metadata_pb2


class Cache(object):
    def __init__(self, func):
        self.func = func

    def __get__(self, obj, objtype=None):
        if obj is None:
            return self.func
        return partial(self, obj)

    def __call__(self, *args, **kw):
        obj = args[0]
        try:
            cache = obj.__cache
        except AttributeError:
            cache = obj.__cache = {}

        arglist = list(args[1:])
        for i in xrange(0, len(arglist)):
            if type(arglist[i]) == list:
                astring = True
                for item in arglist[i]:
                    if type(item) != str and type(item) != unicode:
                        astring = False
                        break
                if astring:
                    arglist[i] = "".join(arglist[i])
        arglist = tuple(arglist)

        key = (self.func, arglist, frozenset(kw.items()))
        try:
            res = cache[key]
        except KeyError:
            res = cache[key] = self.func(*args, **kw)
        return res


class SpotifyCacheManager():
    def __init__(self):
        self.track_cache = {}
        self.album_cache = {}
        self.artist_cache = {}

    def get(self, uri):
        cache = {
            "track": self.track_cache,
            "album": self.album_cache,
            "artist": self.artist_cache,
        }

        uri_type = SpotifyUtil.get_uri_type(uri)
        if uri_type not in cache:
            return False


class SpotifyObject():
    def __str__(self):
        return unicode(self)

    def __unicode__(self):
        return self.getName()

    def getID(self):
        return SpotifyUtil.gid2id(self.obj.gid)

    def getURI(self):
        return SpotifyUtil.gid2uri(self.uri_type, self.obj.gid)


class SpotifyMetadataObject(SpotifyObject):
    def __init__(self, spotify, uri=None, obj=None):
        if obj is not None:
            self.obj = obj
        else:
            self.obj = spotify.api.metadata_request(uri)
        self.spotify = spotify

    def getName(self):
        return self.obj.name

    def getPopularity(self):
        return self.obj.popularity


class SpotifyTrack(SpotifyMetadataObject):
    uri_type = "track"
    replaced = False

    @Cache
    def isAvailable(self, country=None):
        country = self.spotify.api.country if country is None else country
        new_obj = self.spotify.api.recurse_alternatives(self.obj, country=country)
        if not new_obj:
            return False
        else:
            # invalidate cache
            self._Cache__cache = {}

            if not new_obj.HasField("name"):
                new_obj = self.spotify.api.metadata_request(SpotifyUtil.gid2uri("track", new_obj.gid))
            self.old_obj = self.obj
            self.obj = new_obj
            self.replaced = True
            return True

    def setStarred(self, starred=True):
        self.spotify.api.set_starred(self.getURI(), starred)

    def getNumber(self):
        return self.obj.number

    def getDiscNumber(self):
        return self.obj.disc_number

    def getDuration(self):
        return self.obj.duration

    def getFileURL(self, urlOnly=True):
        resp = self.spotify.api.track_uri(self.obj)

        if False != resp and "uri" in resp:
            return resp["uri"] if urlOnly else resp
        else:
            return False

    @Cache
    def getAlbum(self, nameOnly=False):
        if nameOnly:
            return self.obj.album.name
        else:
            return self.spotify.objectFromInternalObj("album", self.obj.album)[0]

    @Cache
    def getArtists(self, nameOnly=False):
        return self.spotify.objectFromInternalObj("artist", self.obj.artist, nameOnly)


class SpotifyArtist(SpotifyMetadataObject):
    uri_type = "artist"

    def getPortraits(self):
        return Spotify.imagesFromArray(self.obj.portrait)

    def getBiography(self):
        return self.obj.biography[0].text if len(self.obj.biography) else None

    def getNumTracks(self):
        # this means the number of top tracks, really
        return len(self.getTracks(objOnly=True))

    def getRelatedArtists(self, nameOnly=False):
        return self.spotify.objectFromInternalObj("artist", self.obj.related, nameOnly)

    @Cache
    def getTracks(self, objOnly=False):
        top_tracks = []

        for obj in self.obj.top_track:
            if obj.country == self.spotify.api.country:
                top_tracks = obj

        if objOnly:
            return top_tracks.track

        if len(top_tracks.track) == 0:
            return None

        return self.spotify.objectFromInternalObj("track", top_tracks.track)


class SpotifyAlbum(SpotifyMetadataObject):
    uri_type = "album"

    def getLabel(self):
        return self.obj.label

    @Cache
    def getArtists(self, nameOnly=False):
        return self.spotify.objectFromInternalObj("artist", self.obj.artist, nameOnly)

    def getCovers(self):
        return Spotify.imagesFromArray(self.obj.cover)

    def getNumDiscs(self):
        return len(self.obj.disc)

    def getNumTracks(self):
        return len(self.getTracks(objOnly=True))

    @Cache
    def getTracks(self, disc_num=None, objOnly=False):
        track_objs = []

        for disc in self.obj.disc:
            if disc.number == disc_num or disc_num is None:
                track_objs += disc.track

        if objOnly:
            return track_objs

        if len(track_objs) == 0:
            return None

        return self.spotify.objectFromInternalObj("track", track_objs)


class SpotifyPlaylist(SpotifyObject):
    uri_type = "playlist"
    refs = []

    def __init__(self, spotify, uri):
        self.spotify = spotify
        self.obj = spotify.api.playlist_request(uri)
        self.uri = uri
        SpotifyPlaylist.refs.append(self)

    def __getitem__(self, index):
        if index >= self.getNumTracks():
            raise IndexError

        return self.getTracks()[index]

    def __len__(self):
        return self.getNumTracks()

    def reload(self):
        self._Cache__cache = {}
        self.obj = self.spotify.api.playlist_request(self.uri)

    def reload_refs(self):
        for playlist in self.refs:
            if playlist.getURI() == self.uri:
                playlist.reload()

    def getID(self):
        uri_parts = self.uri.split(":")
        if len(uri_parts) == 4:
            return uri_parts[3]
        else:
            return uri_parts[4]

    def getURI(self):
        return self.uri

    def getName(self):
        return "Starred" if self.getID() == "starred" else self.obj.attributes.name

    def rename(self, name):
        ret = self.spotify.api.rename_playlist(self.getURI(), name)
        self.reload_refs()
        return ret

    def addTracks(self, tracks):
        tracks = [tracks] if type(tracks) != list else tracks
        uris = [track.getURI() for track in tracks]

        uris_str = ",".join(uris)
        self.spotify.api.playlist_add_track(self.getURI(), uris_str)

        self.reload_refs()

    def removeTracks(self, tracks):
        tracks = [tracks] if type(tracks) != list else tracks

        uris = []
        for track in tracks:
            if track.replaced:
                uris.append(SpotifyUtil.gid2uri("track", track.old_obj.gid))
            else:
                uris.append(self.getURI())

        self.spotify.api.playlist_remove_track(self.getURI(), uris)

        self.reload_refs()

    def getNumTracks(self):
        # we can't rely on the stated length, some might not be available
        return len(self.getTracks())

    @Cache
    def getTracks(self):
        track_uris = [item.uri for item in self.obj.contents.items]
        tracks = self.spotify.objectFromURI(track_uris, asArray=True)

        if self.obj.contents.truncated:
            def work_function(spotify, uri, start, tracks):
                track_uris = [item.uri for item in spotify.api.playlist_request(uri, start).contents.items]
                tracks += spotify.objectFromURI(track_uris, asArray=True)

            results = {}
            jobs = []
            tracks_per_call = 100
            start = tracks_per_call
            while start < self.obj.length:
                results[start] = []
                jobs.append((self.spotify, self.uri, start, results[start]))
                start += tracks_per_call

            Spotify.doWorkerQueue(work_function, jobs)

            for k, v in sorted(results.items()):
                tracks += v

        return tracks


class SpotifyUserlist():
    def __init__(self, spotify, name, tracks):
        self.spotify = spotify
        self.name = name
        self.tracks = tracks

    def __getitem__(self, index):
        if index >= self.getNumTracks():
            raise IndexError

        return self.getTracks()[index]

    def __len__(self):
        return self.getNumTracks()

    def getID(self):
        return None

    def getURI(self):
        return None

    def getName(self):
        return self.name

    def getNumTracks(self):
        return len(self.tracks)

    def getTracks(self):
        return self.tracks


class SpotifySearch():
    def __init__(self, spotify, query, query_type, max_results, offset):
        self.spotify = spotify
        self.query = query
        self.query_type = query_type
        self.max_results = max_results
        self.offset = offset
        self.populate()

    def populate(self):
        xml = self.spotify.api.search_request(self.query, query_type=self.query_type, max_results=self.max_results, offset=self.offset)
        xml = xml[38:]  # trim UTF8 declaration
        self.result = etree.fromstring(xml)

        # invalidate cache
        self._Cache__cache = {}

    def next(self):
        self.offset += self.max_results
        self.populate()

    def prev(self):
        self.offset = self.offset - self.max_results if self.offset >= self.max_results else 0
        self.populate()

    def getName(self):
        return "Search "+self.query_type+": "+self.query

    def getTracks(self):
        return self.getObjByID(self.result, "track")

    def getNumTracks(self):
        return len(self.getTracks())

    def getAlbums(self):
        return self.getObjByID(self.result, "album")

    def getArtists(self):
        return self.getObjByID(self.result, "artist")

    def getPlaylists(self):
        return self.getObjByURI(self.result, "playlist")

    def getObjByID(self, result, obj_type):
        elems = result.find(obj_type+"s")
        if elems is None:
            elems = []
        ids = [elem[0].text for elem in list(elems)]
        objs = self.spotify.objectFromID(obj_type, ids)
        return objs

    def getObjByURI(self, result, obj_type):
        elems = result.find(obj_type+"s")
        if elems is None:
            elems = []
        uris = [elem[0].text for elem in list(elems)]
        objs = self.spotify.objectFromURI(uris, asArray=True)
        return objs


class SpotifyToplist():
    def __init__(self, spotify, toplist_content_type, toplist_type, username, region):
        self.spotify = spotify
        self.toplist_type = toplist_type
        self.toplist_content_type = toplist_content_type
        self.username = username
        self.region = region
        self.toplist = self.spotify.api.toplist_request(toplist_content_type, toplist_type, username, region)

    def getTracks(self):
        if self.toplist_content_type != "track":
            return []
        return self.spotify.objectFromID(self.toplist_content_type, self.toplist.items)

    def getAlbums(self):
        if self.toplist_content_type != "album":
            return []
        return self.spotify.objectFromID(self.toplist_content_type, self.toplist.items)

    def getArtists(self):
        if self.toplist_content_type != "artist":
            return []
        return self.spotify.objectFromID(self.toplist_content_type, self.toplist.items)


class Spotify():
    AUTOREPLACE_TRACKS = True

    def __init__(self, username, password):
        self.api = SpotifyAPI()
        self.api.connect(username, password)

    def logged_in(self):
        return self.api.is_logged_in and not self.api.disconnecting

    def logout(self):
        self.api.disconnect()

    @Cache
    def getPlaylists(self, username=None):
        username = self.api.username if username is None else username
        playlist_uris = []
        if username == self.api.username:
            playlist_uris += ["spotify:user:"+username+":starred"]

        playlist_uris += [playlist.uri for playlist in self.api.playlists_request(username).contents.items]
        return self.objectFromURI(playlist_uris)

    def newPlaylist(self, name):
        self._Cache__cache = {}

        uri = self.api.new_playlist(name)
        return SpotifyPlaylist(self, uri=uri)

    def removePlaylist(self, playlist):
        self._Cache__cache = {}
        return self.api.remove_playlist(playlist.getURI())

    def getUserToplist(self, toplist_content_type="track", username=None):
        return SpotifyToplist(self, toplist_content_type, "user", username, None)

    def getRegionToplist(self, toplist_content_type="track", region=None):
        return SpotifyToplist(self, toplist_content_type, "region", None, region)

    def search(self, query, query_type="all", max_results=50, offset=0):
        return SpotifySearch(self, query, query_type=query_type, max_results=max_results, offset=offset)

    def objectFromInternalObj(self, object_type, objs, nameOnly=False):
        if nameOnly:
            return ", ".join([obj.name for obj in objs])

        try:
            uris = [SpotifyUtil.gid2uri(object_type, obj.gid) for obj in objs]
        except:
            uris = SpotifyUtil.gid2uri(object_type, objs.gid)

        return self.objectFromURI(uris, asArray=True)

    def objectFromID(self, object_type, ids):
        try:
            uris = [SpotifyUtil.id2uri(object_type, id) for id in ids]
        except:
            uris = SpotifyUtil.id2uri(object_type, ids)

        return self.objectFromURI(uris, asArray=True)

    @Cache
    def objectFromURI(self, uris, asArray=False):
        if not self.logged_in():
            return False

        uris = [uris] if type(uris) != list else uris
        if len(uris) == 0:
            return [] if asArray else None

        uri_type = SpotifyUtil.get_uri_type(uris[0])
        if not uri_type:
            return [] if asArray else None
        elif uri_type == "playlist":
            if len(uris) == 1:
                results = [SpotifyPlaylist(self, uri=uris[0])]
            else:
                thread_results = {}
                jobs = []
                for index in range(0, len(uris)):
                    jobs.append((self, uris[index], thread_results, index))

                def work_function(spotify, uri, results, index):
                    results[index] = SpotifyPlaylist(spotify, uri=uri)

                Spotify.doWorkerQueue(work_function, jobs)

                results = [v for k, v in thread_results.items()]

        elif uri_type in ["track", "album", "artist"]:
            uris = [uri for uri in uris if not SpotifyUtil.is_local(uri)]
            objs = self.api.metadata_request(uris)
            objs = [objs] if type(objs) != list else objs

            failed_requests = len([obj for obj in objs if False == obj])
            if failed_requests > 0:
                print failed_requests, "metadata requests failed"

            objs = [obj for obj in objs if False != obj]
            if uri_type == "track":
                tracks = [SpotifyTrack(self, obj=obj) for obj in objs]
                results = [track for track in tracks if False == self.AUTOREPLACE_TRACKS or track.isAvailable()]
            elif uri_type == "album":
                results = [SpotifyAlbum(self, obj=obj) for obj in objs]
            elif uri_type == "artist":
                results = [SpotifyArtist(self, obj=obj) for obj in objs]
        else:
            return [] if asArray else None

        if not asArray:
            if len(results) == 1:
                results = results[0]
            elif len(results) == 0:
                return [] if asArray else None

        return results

    @staticmethod
    def doWorkerQueue(work_function, args, worker_thread_count=5):
        def worker():
            while not q.empty():
                args = q.get()
                work_function(*args)
                q.task_done()

        q = Queue()
        for arg in args:
            q.put(arg)

        for i in range(worker_thread_count):
            t = Thread(target=worker)
            t.start()
        q.join()

    @staticmethod
    def imagesFromArray(image_objs):
        images = {}
        for image_obj in image_objs:
            size = str(image_obj.width)
            images[size] = "https://d3rt1990lpmkn.cloudfront.net/" + size + "/" + SpotifyUtil.gid2id(image_obj.file_id)

        return images
