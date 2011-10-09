"""
This contains the various models used in ProjectTelescope, defining the attributes of each.
"""

import datetime
import telescope

class Peer(object):
    """
    The basic peer object, stored within Torrents.
    """
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
        """
        Allows a dictionary to be passed and parsed into a Peer object.
        """
        self.__dict__.update(entries)

    def to_dict(self):
        """
        Allows Peer object to be converted back into a dictionary.

        This also works with incomplete Peer objects, thanks to the voodoo below.
        """
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
    """
    Boring User object.
    """
    user_id = -1
    can_leech = False
    is_anonymous = False

    def __init__(self, **entries):
        """
        Allows a dictionary to be passed and parsed into a User object.
        """
        self.__dict__.update(entries)


class AnonymousUser(User):
    """
    An anonymous user, inheriting from User that just changes the default for is_anonymous.
    """
    is_anonymous = True


class Torrent(object):
    """
    A Torrent object. This is the heart and soul of Telescope.

    It would be wise not to modify the attributes directly.

    The # rw annotation indicates which of the attributes can be modified by the functions below.
    """
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
        """
        Convert a passed-in dictionary into a Torrent object.
        """
        self.__dict__.update(entries)

    def add_peer(self, who, seeder=False):
        """
        Inform backend storage of a new peer
        """
        telescope.STORAGE.torrent_add_peer(self, who, seeder)
        self.peers[who.peer_id.encode('hex')] = who
        if seeder:
            self.seeders.append(who.peer_id.encode('hex'))
        else:
            self.leechers.append(who.peer_id.encode('hex'))

    def nuke_peer(self, peer):
        """
        Inform backend storage to remove a peer
        """
        telescope.STORAGE.torrent_del_peer(self, peer)
        pid = peer.peer_id.encode('hex')
        del self.peers[pid]
        if pid in self.seeders:
            self.seeders.remove(pid)
        if pid in self.leechers:
            self.leechers.remove(pid)

    def flip_peer(self, peer):
        """
        Inform backend storage that a peer has completed their download and is now seeding
        """
        telescope.STORAGE.torrent_flip_peer(self, peer)

    def incr_balance(self, howmuch):
        """
        Increment the torrent's "balance"

        (note: this must also allow negative values)
        """
        telescope.STORAGE.torrent_increment_balance(self, howmuch)

    def incr_completed(self):
        """
        Increment the torrent's completed download count by one
        """
        telescope.STORAGE.torrent_increment_completed(self)
