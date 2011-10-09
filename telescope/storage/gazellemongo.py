"""
StorageGazelle provides the Telescope <-> Mongo <-> Gazelle system.

Applicable documentation for many of the fields can be found in the abstract.py file
"""

import pymongo, logging
import pymongo.binary
from telescope.storage.abstract import StorageAbstract
from telescope.models import *

class StorageGazelle(StorageAbstract):
    WHITELIST = []
    MONGO_HANDLE = None

    def __init__(self, config):
        self.MONGO_CONFIG = config

    def lookup_user(self, key):
        mh = self.MONGO_HANDLE.users.find_one({"_id": key})
        if mh is None:
            return AnonymousUser()
        return User(**mh)

    def lookup_torrent(self, key):
        mh = self.MONGO_HANDLE.torrents.find_one({"_id": key.encode("hex")})
        if mh is None:
            return False
        return Torrent(**mh)

    # Loading data
    def load_data(self):
        logging.debug("Preparing to connect to Mongo!")
        self.MONGO_HANDLE = pymongo.Connection(*self.MONGO_CONFIG['connection'])
        self.MONGO_HANDLE = self.MONGO_HANDLE[self.MONGO_CONFIG['database']]
        wl_cursor = self.MONGO_HANDLE.whitelist.find({'fields': ['peer_id']})
        for peer_id in wl_cursor:
            self.WHITELIST.append(peer_id)
        logging.debug("Loaded %d items from the whitelist." % (len(self.WHITELIST),))
        logging.debug("Connection complete")

    def check_peer(self, nam):
        for thing in self.WHITELIST:
            if nam.startswith(thing):
                return True
        return False

    def record_snatch(self, user, torrent, peer, time_now):
        insertObj = {
            'user_id': user.user_id,
            'torrent_id': torrent.torrent_id,
            'time_now': time_now,
            'ip': peer.ip if '.' in peer.ip else '0.0.0.0'
        }
        self.MONGO_HANDLE.snatch_log.insert(insertObj)

    def record_torrent(self, torrent, snatched):
        torrent.last_flushed = datetime.datetime.now()
        self.MONGO_HANDLE.torrents.update({'_id': torrent.info_hash.encode('hex')},
                {'$set': {'last_flushed': torrent.last_flushed}})
        insertObj = {
            'torrent_id': torrent.torrent_id,
            'seeders': len(torrent.seeders),
            'leechers': len(torrent.leechers),
            'snatched': snatched,
            'balance': torrent.balance
        }
        self.MONGO_HANDLE.torrent_log.insert(insertObj)

    def record_peer(self, peer, torrent, user, active):
        logging.debug("Peer log by %d on %d" % (user.user_id, torrent.torrent_id))
        insertObj = {
            'user_id': user.user_id,
            'torrent_id': torrent.torrent_id,
            'active': active,
            'uploaded': peer.uploaded,
            'downloaded': peer.downloaded,
            'upspeed': peer.upspeed,
            'downspeed': peer.downspeed,
            'left': peer.left,
            'announcing_for': (datetime.datetime.now() - peer.first_announced).total_seconds(),
            'announces': peer.announces,
            'ip': peer.ip if '.' in peer.ip else '0.0.0.0',
            'peer_id': pymongo.binary.Binary(peer.peer_id),
            'ua': peer.ua
        }
        self.MONGO_HANDLE.peer_log.insert(insertObj)

    def record_user(self, user, download_ch, upload_ch):
        logging.debug("User log by %d: %d dl/%d ul" % (user.user_id, download_ch, upload_ch))
        insertObj = {
            'user_id': user.user_id,
            'download_change': download_ch,
            'upload_change': upload_ch
        }
        self.MONGO_HANDLE.user_log.insert(insertObj)

    def torrent_add_peer(self, torrent, peer, seeder):
        logging.debug("Adding new peer to torrent %s" % (torrent.info_hash.encode('hex'),))
        perfm = {"$set": {"peers.%s" % (peer.peer_id.encode('hex')): peer.to_dict()},
                 "$addToSet": {("seeders" if seeder else "leechers"): peer.peer_id.encode('hex')}}
        self.MONGO_HANDLE.torrents.update({'_id': torrent.info_hash.encode('hex')}, perfm)

    def torrent_flip_peer(self, torrent, peer):
        addTo = "seeders"
        delFrom = "leechers"
        if peer.left > 0:
            addTo = "leechers"
            delFrom = "seeders"
        self.MONGO_HANDLE.torrents.update({'_id': torrent.info_hash.encode('hex')},
                {"$pullAll": {delFrom: [peer.peer_id.encode('hex')]}, "$addToSet": {addTo: peer.peer_id.encode('hex')}})

    def torrent_del_peer(self, torrent, peer):
        self.MONGO_HANDLE.torrents.update({'_id': torrent.info_hash.encode('hex')},
                {"$unset": {"peers.%s" % (peer.peer_id.encode('hex')): 1},
                 "$pullAll": {"seeders": [peer.peer_id.encode('hex')], "leechers": [peer.peer_id.encode('hex')]}})

    def torrent_increment_balance(self, torrent, howmuch):
        self.MONGO_HANDLE.torrents.update({'_id': torrent.info_hash.encode('hex')}, {"$inc": {"balance": howmuch}})

    def torrent_increment_completed(self, torrent):
        self.MONGO_HANDLE.torrents.update({'_id': torrent.info_hash.encode('hex')}, {"$inc": {"completed": 1}})

    def encode_binary(self, inp):
        return pymongo.binary.Binary(inp)
