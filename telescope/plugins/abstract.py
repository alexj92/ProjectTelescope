from yapsy.IPlugin import IPlugin

class ITelescopePlugin(IPlugin):
    pass

class ITelescopeWebPlugin(IPlugin):
    """
    WebPlugins are expected to register themselves within their activate() methods using
    bottle.route
    """
    pass

class TelescopeAnnounceState(object):
    torrent = None
    peer = None
    user = None

    def __init__(self, torrent, peer, user, **extra):
        self.torrent = torrent
        self.peer = peer
        self.user = user
        self.__dict__.update(extra)

class ITelescopeAnnouncePlugin(IPlugin):
    def start_announce(self, tas):
        """
        Called immediately after the peer has been found.
        """
        return

    def end_announce(self, tas):
        """
        Called immediately before the final result is sent.
        """
        return

class ITelescopeMasterPlugin(IPlugin):
    def pending_cycle(self, dbo, dbb):
        """
        Called when the master goes through its pending action cycle.
        """
        return

    def cleanup_cycle(self, dbo, dbb):
        """
        Called when the master goes through its cleanup cycle.
        """
        return
