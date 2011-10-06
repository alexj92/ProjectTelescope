import datetime
import telescope

class Peer(object):
    user_id = -1
    peer_id = '______'
    ua = 'Peer-lookup-failed/0.1'
    ip = '0.0.0.0'
    ipv6 = None
    port = 0
    ipport = '123456'
    ipv6port = None
    uploaded = -1
    downloaded = -1
    left = -1
    last_announced = -1
    first_announced = -1
    announces = 0
    upspeed = 0
    downspeed = 0

    def __init__(self, **entries):
        self.__dict__.update(entries)

    def to_dict(self):
        self.announces = 90000
        output = dict(vars(self.__class__))
        check = []
        for k in output.keys():
            if not k.startswith('__') and not hasattr(output[k], '__call__'):
                check.append(k)
        mainbase = vars(self.__class__)
        allyourbase = vars(self)
        output = {}
        for k in check:
            output[k] = allyourbase[k] if k in allyourbase.keys() else mainbase[k]
            # peer ID needs encoding
            if output[k] is not None and (k == 'peer_id' or k == 'ipport' or k == 'ipv6port'):
                output[k] = telescope.STORAGE.encode_binary(output[k])
        return output

class User(object):
    user_id = -1
    can_leech = False
    is_anonymous = False

    def __init__(self, **entries):
        self.__dict__.update(entries)

class AnonymousUser(User):
    is_anonymous = True

class Torrent(object):
    torrent_id = -1
    last_seeded = -1
    balance = 0 # rw
    completed = 0 # rw
    free_torrent = False
    peers = {} # rw
    seeders = [] # rw
    leechers = [] # rw
    last_flushed = datetime.datetime.fromtimestamp(0)

    def __init__(self, **entries):
        self.__dict__.update(entries)

    def add_peer(self, who, seeder=False):
        telescope.STORAGE.torrent_add_peer(self, who, seeder)
        self.peers[who.peer_id.encode('hex')] = who
        if seeder:
            self.seeders.append(who.peer_id.encode('hex'))
        else:
            self.leechers.append(who.peer_id.encode('hex'))

    def nuke_peer(self, peer):
        telescope.STORAGE.torrent_del_peer(self, peer)
        pid = peer.peer_id.encode('hex')
        del self.peers[pid]
        if pid in self.seeders:
            self.seeders.remove(pid)
        if pid in self.leechers:
            self.leechers.remove(pid)

    def flip_peer(self, peer):
        telescope.STORAGE.torrent_flip_peer(self, peer)

    def incr_balance(self, howmuch):
        telescope.STORAGE.torrent_increment_balance(self, howmuch)

    def incr_completed(self):
        telescope.STORAGE.torrent_increment_completed(self)
