"""
Abstract Storage class
"""

class StorageAbstract(object):
    """
    Abstract class for Telescope's storage system
    """

    def lookup_user(self, key):
        """
        Find a user by it's database ID.
        """
        raise NotImplementedError, "lookup_user has not been defined"

    def lookup_torrent(self, key):
        """
        Find a torrent by it's database ID.
        """
        raise NotImplementedError, "lookup_torrent has not been defined"

    def load_data(self):
        """
        Connect to the database and load/cache any required data.
        """
        raise NotImplementedError, "load_data has not been defined"

    def check_peer(self, nam):
        """
        Check that a peer ID (specified by nam) is okay.

        Returns True for yes, False for no.
        """
        raise NotImplementedError, "check_peer has not been defined"

    def record_snatch(self, user, torrent, peer, time_now):
        """
        Record a snatch by peer (which is user's peer) against torrent at time_now.
        """
        raise NotImplementedError, "record_snatch has not been defined"

    def record_peer(self, peer, torrent, user, active):
        """
        Record an updated torrent into storage.
        """
        raise NotImplementedError, "record_torrent has not been defined"

    def record_peer(self, peer, torrent, user):
        """
        Record a peer's information.
        """
        raise NotImplementedError, "record_peer has not been defined"

    def record_user(self, user, download_ch, upload_ch):
        """
        Record a user's download/upload.
        """
        raise NotImplementedError, "record_user has not been defined"

    def torrent_add_peer(self, torrent, peer, seeder):
        """
        Add a new peer to a torrent.
        """
        raise NotImplementedError, "torrent_add_peer has not been defined"

    def torrent_flip_peer(self, torrent, peer):
        """
        Change a seeder into a leecher or a leecher into a seeder.
        """
        raise NotImplementedError, "torrent_flip_peer has not been defined"

    def torrent_del_peer(self, torrent, peer):
        """
        Remove a peer from a torrent.
        """
        raise NotImplementedError, "torrent_del_peer has not been defined"

    def torrent_increment_balance(self, torrent, howmuch):
        """
        Increment the balance on a torrent.
        """
        raise NotImplementedError, "torrent_increment_balance has not been defined"

    def torrent_increment_completed(self, torrent):
        """
        Increment the download completed count on a torrent.
        """
        raise NotImplementedError, "torrent_increment_completed has not been defined"

    def encode_binary(self, inp):
        """
        Encode in a storage backend-specific manner certain binary fields.
        """
        raise NotImplementedError, "encode_binary has not been defined"
