class StorageAbstract(object):
    def lookup_user(self, key):
        return AnonymousUser()

    def lookup_torrent(self, key):
        return False

    def load_data(self):
        pass

    def check_peer(self, nam):
        pass

    def record_snatch(self, user, torrent, peer, time_now):
        pass

    def record_torrent(self, torrent, snatched):
        pass

    def record_peer(self, peer, torrent, user):
        pass

    def torrent_add_peer(self, torrent, peer, seeder):
        pass

    def torrent_flip_peer(self, torrent, peer):
        pass

    def torrent_del_peer(self, torrent, peer):
        pass

    def torrent_increment_balance(self, torrent, howmuch):
        pass

    def torrent_increment_completed(self, torrent):
        pass

    def encode_binary(self, inp):
        pass
