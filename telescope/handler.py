import bottle, logging
import datetime, random
import socket, struct
import telescope
from telescope.utilities import *

STORAGE = telescope.STORAGE
@bottle.route('/')
def index():
    return 'There is nothing here.'

@bottle.route('/:key/scrape')
@bottle.route('/:key/scrape/')
@check_key
@required_params(['info_hash'])
@check_params(['info_hash'])
def scrape(user):
    pass


@bottle.route('/:key/announce/')
@bottle.route('/:key/announce')
@check_key
@required_params(['info_hash', 'peer_id', 'left', 'uploaded', 'downloaded', 'port'])
@check_params(['info_hash', 'peer_id', 'numwant'])
def announce(user):
    time_now = datetime.datetime.now()

    q = bottle.request.query
    update_torrent_in_db = False
    # do we track this torrent?
    torrent = STORAGE.lookup_torrent(q['info_hash'])
    if not torrent:
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

    peer.upspeed = peer.downspeed = 0

    uploaded = int(q['uploaded'])
    downloaded = int(q['downloaded'])
    #print "New upload is %d, new download is %d" % (uploaded, downloaded)
    #print "New_peer? %s" % (str(new_peer),)
    #print "Event? %s" % (q['event'] if 'event' in q.keys() else 'NO EVENT')
    if new_peer or ('event' in q.keys() and q['event'] == "started") or uploaded < peer.uploaded or downloaded > peer.downloaded:
        peer.user_id = user.user_id
        peer.peer_id = q['peer_id']
        peer.uploaded = int(q['uploaded'])
        peer.downloaded = int(q['downloaded'])
        peer.left = int(q['left'])
        peer.first_announced = peer.last_announced = time_now 
        peer.ua = bottle.request.headers.get('User-Agent', 'Lookup-Failed/1.0')
        peer.announces = 1
    else:
        peer.announces += 1
        
        upload_change = 0
        download_change = 0
        #print "Previous upload was %d, previous download was %d" % (peer.uploaded, peer.downloaded)
        if uploaded != peer.uploaded:
            upload_change = uploaded - peer.uploaded
            peer.uploaded = uploaded

        if downloaded != peer.downloaded:
            download_change = downloaded - peer.downloaded
            peer.downloaded = downloaded

        #print "Upload change is %d, download change is %d" % (upload_change, download_change)

        if upload_change != 0 or download_change != 0:
            corrupt = int(q['corrupt']) if 'corrupt' in q.keys() else 0
            torrent.incr_balance(torrent.balance + upload_change - download_change - corrupt)
            update_torrent_in_db = True

            if time_now > peer.last_announced:
                peer.upspeed = upload_change / int((time_now - peer.last_announced).total_seconds())
                peer.downspeed = download_change / int((time_now - peer.last_announced).total_seconds())

            if torrent.free_torrent:
                download_change = 0
            #print "Upload change is %d, download change is %d" % (upload_change, download_change)

            if upload_change != 0 or download_change != 0:
                STORAGE.record_user(user, upload_change, download_change)

            

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
    # DO NOT MANIPULATE PEER BEYOND THIS POINT
    if int(q['left']) > 0 or ('event' in q.keys() and q['event'] == 'completed'):
        torrent.add_peer(peer, False)
    else:
        torrent.add_peer(peer, True)

    numwant = 50
    if 'numwant' in q.keys():
        numwant = int(q['numwant'])

    snatched = False
    active = True
    if 'event' in q.keys() and q['event'] == 'stopped':
        update_torrent_in_db = True
        active = False
        numwant = 0

        if peer.peer_id.encode('hex') in torrent.peers.keys():
            torrent.nuke_peer(peer)
    elif 'event' in q.keys() and q['event'] == 'completed':
        snatched = True
        update_torrent_in_db = True
        torrent.incr_completed()

        STORAGE.record_snatch(user, torrent, peer, time_now)

        torrent.flip_peer(peer)

    if 'compact' in q.keys() and q['compact'] == '1':
        peerd = format_compact(peer, torrent, numwant)
    else:
        peerd = format_normal(peer, torrent, numwant, ('no_peer_id' in q.keys() and q['no_peer_id'] == 1))

    if update_torrent_in_db or torrent.last_flushed + datetime.timedelta(0, 3600) < time_now:
        STORAGE.record_torrent(torrent, snatched)


    STORAGE.record_peer(peer, torrent, user, active)

    return "d8:intervali%de12:min intervali%de5:peers%s8:completei%de10:incompletei%de10:downloadedi%dee" % (telescope.CONFIG['announce interval'], telescope.CONFIG['min interval'], peerd, len(torrent.seeders), len(torrent.leechers), torrent.completed)

def select_people(torrent, select_seeders = True, num = 50):
    selector = torrent.seeders if select_seeders else torrent.leechers
    resp = random.sample(selector, min(num, len(selector)))
    return resp
        

def format_compact(peer, torrent, num):
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
    

def format_normal(peer, torrent, num, no_peer_id = False):
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
