"""
This is the core HTTP handler of Telescope.
"""

import  logging, bottle
import datetime, random
import socket, struct
from telescope.errors import *
from telescope.utilities import *

STORAGE = telescope.STORAGE

@bottle.route('/')
def index():
    """
    Default / route, in case someone decides to navigate to the tracker root.
    """
    return 'There is nothing here.'


@bottle.route('/:key/scrape')
@bottle.route('/:key/scrape/')
@check_key
@required_params(['info_hash'])
@check_params(['info_hash'])
def scrape(user):
    """
    Handle torrent scraping
    """
    pass


@bottle.route('/:key/announce/')
@bottle.route('/:key/announce')
@check_key
@required_params(['info_hash', 'peer_id', 'left', 'uploaded', 'downloaded', 'port'])
@check_params(['info_hash', 'peer_id', 'numwant'])
def announce(user):
    """
    Handle announces. This is the main, most important pieces, of Telescope.
    """
    time_now = datetime.datetime.now()

    q = bottle.request.query
    update_torrent_in_db = False
    # do we track this torrent?
    torrent = STORAGE.lookup_torrent(q['info_hash'])
    if not torrent:
        # we don't
        fail(REASON_UNREGISTERED_TORRENT)

    # we do!

    # is leeching off?
    if long(q['left']) > 0:
        if not user.can_leech:
            fail(REASON_LEECHING_FORBIDDEN)

    # now find the peer
    new_peer = False
    peer = None
    p_id = q['peer_id'].encode('hex')
    if p_id not in torrent.peers.keys():
        new_peer = True
        peer = Peer()
    else:
        peer = conjure_peer(torrent.peers[p_id])
        peer.last_announced = time_now

    # as yet, no download/upload speed
    peer.upspeed = peer.downspeed = 0

    uploaded = int(q['uploaded'])
    downloaded = int(q['downloaded'])
    if new_peer or (
        'event' in q.keys() and q['event'] == "started") or uploaded < peer.uploaded or downloaded < peer.downloaded:
        # if they're new,
        # or they've just started downloading
        # or they've provided us with a new uploaded value less than what they've already told us
        # or they've given us a new downloaded value less than what they've told us
        # resync the peer object's data
        peer.user_id = user.user_id
        peer.peer_id = q['peer_id']
        peer.uploaded = int(q['uploaded'])
        peer.downloaded = int(q['downloaded'])
        peer.left = int(q['left'])
        peer.first_announced = peer.last_announced = time_now
        peer.ua = bottle.request.headers.get('User-Agent', 'Lookup-Failed/1.0')
        peer.announces = 1
    else:
        # otherwise, just increment the announce count
        peer.announces += 1

        upload_change = 0
        download_change = 0
        #print "Previous upload was %d, previous download was %d" % (peer.uploaded, peer.downloaded)
        if uploaded != peer.uploaded:
            # if the upload isn't the same, then calculate delta uploaded
            upload_change = uploaded - peer.uploaded
            peer.uploaded = uploaded

        if downloaded != peer.downloaded:
            # if the download isn't the same, calculate delta downloaded
            download_change = downloaded - peer.downloaded
            peer.downloaded = downloaded

        #print "Upload change is %d, download change is %d" % (upload_change, download_change)

        # if they uploaded or downloaded anything since the last announce...
        if upload_change != 0 or download_change != 0:
            # find how much they say was corrupt data
            corrupt = int(q['corrupt']) if 'corrupt' in q.keys() else 0
            # ...and increment the torrent balance count
            torrent.incr_balance(torrent.balance + upload_change - download_change - corrupt)
            update_torrent_in_db = True

            if time_now > peer.last_announced:
                # if this announce is after their last one,
                # update their upload/download speed
                peer.upspeed = upload_change / int((time_now - peer.last_announced).total_seconds())
                peer.downspeed = download_change / int((time_now - peer.last_announced).total_seconds())

            if torrent.free_torrent:
                # if it's free, treat it as if they haven't downloaded anything
                download_change = 0

            if upload_change != 0 or download_change != 0:
                # if they've STILL uploaded/downloaded anything,
                # record it into storage
                STORAGE.record_user(user, upload_change, download_change)

    # this section handles storing their IP
    skyport = long(q['port'])
    skyip = bottle.request.environ.get('REMOTE_ADDR')
    if 'ip' in q.keys():
        skyip = q['ip']
    elif 'ipv4' in q.keys():
        skyip = q['ipv4']

    skyipv6 = None
    if 'ipv6' in q.keys():
        skyipv6 = q['ipv6']

    if new_peer or peer.port != skyport or peer.ip != skyip:
        peer.port = skyport
        peer.ip = skyip
        clasz = socket.AF_INET if '.' in skyip else socket.AF_INET6
        peer.ipport = socket.inet_pton(clasz, skyip) + struct.pack('>H', skyport) # magic, in a single line

    if skyipv6 is not None and (new_peer or peer.port != skyport or peer.ipv6 != skyipv6):
        peer.ipv6 = skyipv6
        clasz = socket.AF_INET6
        peer.ipv6port = socket.inet_pton(clasz, skyipv6) + struct.pack('>H', skyport)

    # save peer
    # DO NOT MANIPULATE PEER OBJECT BEYOND THIS POINT
    if int(q['left']) > 0 or ('event' in q.keys() and q['event'] == 'completed'):
        torrent.add_peer(peer, False)
    else:
        torrent.add_peer(peer, True)

    # you want peers? how many peers?
    numwant = 50
    if 'numwant' in q.keys():
        numwant = int(q['numwant'])

    snatched = False
    active = True
    if 'event' in q.keys() and q['event'] == 'stopped':
        # they've stopped downloading
        update_torrent_in_db = True
        active = False
        # so they don't want any peers
        numwant = 0

        if peer.peer_id.encode('hex') in torrent.peers.keys():
            # so remove them from the torrent
            torrent.nuke_peer(peer)
    elif 'event' in q.keys() and q['event'] == 'completed':
        # they've completed downloading
        snatched = True
        update_torrent_in_db = True
        # so increment the completion count
        torrent.incr_completed()

        # and record the snatch
        STORAGE.record_snatch(user, torrent, peer, time_now)

        # and make them a seeder
        torrent.flip_peer(peer)

    if 'compact' in q.keys() and q['compact'] == '1':
        # if they want a compact announce, give it to them
        peerd = format_compact(peer, torrent, numwant)
    else:
        # if not, then give it to them straight
        peerd = format_normal(peer, torrent, numwant, ('no_peer_id' in q.keys() and q['no_peer_id'] == 1))

    if update_torrent_in_db or torrent.last_flushed + datetime.timedelta(0, 3600) < time_now:
        # if we haven't flushed for a while, or we need to explicitly dump out data,
        # record the torrent data to storage
        STORAGE.record_torrent(torrent, snatched)

    # record the peer to storage...
    STORAGE.record_peer(peer, torrent, user, active)

    # build the bencoded string
    return "d8:intervali%de12:min intervali%de5:peers%s8:completei%de10:incompletei%de10:downloadedi%dee" % (
        telescope.CONFIG['announce interval'], telescope.CONFIG['min interval'], peerd, len(torrent.seeders),
        len(torrent.leechers), torrent.completed)


def select_people(torrent, select_seeders=True, num=50):
    """
    This function selects num peers from the torrent.

    If select_seeders is True, then we only select seeders
    otherwise, we only select leechers.

    By default we use random.sample, but feel free to implement your own selection system.
    """
    selector = torrent.seeders if select_seeders else torrent.leechers
    resp = random.sample(selector, min(num, len(selector)))
    return resp


def format_compact(peer, torrent, num):
    """
    This function performs the compact announce peerlist building
    """
    rawpeers = select_people(torrent, peer.left > 0, num)
    peers = []
    peers_v6 = []
    for rpeer in rawpeers:
        rpeer = conjure_peer(torrent.peers[rpeer])
        if len(rpeer.ipport) < 18:
            peers.append(rpeer.ipport)
            if rpeer.ipv6port is not None:
                peers_v6.append(rpeer.ipv6port)
        else:
            peers_v6.append(rpeer.ipport)
            # hacks :P
    peers = ''.join(peers)
    peers_v6 = ''.join(peers_v6)
    logging.debug("Telling them about %s" % (peers.encode("hex"),))
    logging.debug("Telling them about %s" % (peers_v6.encode("hex"),))
    return "%d:%s10:peers_ipv6%d:%s" % (len(peers), peers, len(peers_v6), peers_v6)


def format_normal(peer, torrent, num, no_peer_id=False):
    """
    This function performs the 'standard' announce peerlist building
    """
    rawpeers = select_people(torrent, peer.left > 0, num)
    peers = []
    for rpeer in rawpeers:
        if isinstance(torrent.peers[rpeer], dict):
            rpeer = Peer(**torrent.peers[rpeer])
        else:
            rpeer = torrent.peers[rpeer]
        peers.append("d2:ip%d:%s4:port%d:%s" % (len(rpeer.ip), rpeer.ip, len(rpeer.port), rpeer.port))
        if not no_peer_id:
            peers.append("2:id%d:%s" % (len(rpeer.peer_id), rpeer.peer_id))
        peers.append("e")
    return "l%se" % (''.join(peers))
