from telescope.storage.abstract import StorageAbstract
from telescope.models import *

class StorageMock(StorageAbstract):
    """
    Mock class for local testing without a database
    """

    def __init__(self, config):
        return

    def lookup_user(self, key):
        return User(user_id=1, can_leech=True)

    def lookup_torrent(self, key):
        return Torrent(torrent_id=1, last_seeded=1, balance=0, completed=0, free_torrent=False)

    def load_data(self):
        return

    def check_peer(self, nam):
        return True

    def record_snatch(self, user, torrent, peer, time_now):
        return

    def record_torrent(self, torrent, snatched):
        return

    def record_peer(self, peer, torrent, user, active):
        return

    def record_user(self, user, download_ch, upload_ch):
        return

    def torrent_add_peer(self, torrent, peer, seeder):
        return

    def torrent_flip_peer(self, torrent, peer):
        return

    def torrent_del_peer(self, torrent, peer):
        return

    def torrent_increment_balance(self, torrent, howmuch):
        return

    def torrent_increment_completed(self, torrent):
        return

    def encode_binary(self, inp):
        return inp