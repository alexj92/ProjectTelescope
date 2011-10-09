"""
This is the ProjectTelescope master process. This is only required with the GazelleMongo storage backend.
"""

import pymongo
import struct, socket
import time, logging
import pymongo.binary, pymongo.code
import MySQLdb
import MySQLdb.cursors
import datetime

class Struct:
    """
    Allows converting a dictionary into a Python object quickly and easily.
    """

    def __init__(self, **entries):
        self.__dict__.update(entries)


# MAP_REDUCER stores the map function given to MongoDB to find peers that should be culled
MAP_REDUCER = pymongo.code.Code("""function () {
    var outp = {};
    var fa = false;

    var rmBefore = new Date();
    var thatHour = rmBefore.getHours();
    var thatDay = rmBefore.getDate();
    if (thatHour == 0) {
        thatHour = 23;
        if (thatDay == 1) // oh, just give up now <_<
            return;
        thatDay = thatDay - 1;
    } else {
        thatHour = thatHour - 1;
    }
    rmBefore.setDate(thatDay);
    rmBefore.setHours(thatHour);

    for (var a in this.peers) {
        var p = this.peers[a];
        if (p.last_announced <= rmBefore) {
            outp[a] = true;
            fa = true;
        }
    }
    if (fa)
        emit(this._id, outp);
}""")

# This is the reduce function for the above. Doesn't do much.
REDUCER = pymongo.code.Code("""function(k,v) { return 1; }""")

def ip2long (ip):
    """
    Convert a dotted-quad ip address to a network byte order 32-bit integer.


    >>> ip2long('127.0.0.1')
    2130706433

    >>> ip2long('127.1')
    2130706433

    >>> ip2long('127')
    2130706432

    >>> ip2long('127.0.0.256') is None
    True


    Args:
        ip: Dotted-quad ip address (eg. '127.0.0.1')

    Returns:
        Network byte order 32-bit integer or None if ip is invalid
    """
    quads = ip.split('.')
    if len(quads) == 1:
        # only a network quad
        quads = quads + [0, 0, 0]
    elif len(quads) < 4:
        # partial form, last supplied quad is host address, rest is network
        host = quads[-1:]
        quads = quads[:-1] + [0, ] * (4 - len(quads)) + host

    lngip = 0
    for q in quads:
        lngip = (lngip << 8) | int(q)
    return lngip

# Configuration data magically appears when you import telescope
try:
    import telescope
except Exception, e:
    logging.exception(
        "Something went wrong whilst importing the telescope module. Make sure you're running me from outside the telescope/ directory.")
    raise e

if telescope.CONFIG.get('storage', 'not defined') != 'gazellemongo.StorageGazelle':
    logging.error("'storage' is not 'gazellemongo.StorageGazelle' - are you sure you're supposed to be running this?")
    raise Exception("'storage' is not 'gazellemongo.StorageGazelle' - are you sure you're supposed to be running this?")

if 'storage config' not in telescope.CONFIG.keys():
    logging.error("'storage config' is not defined in telescope_config.py")
    raise Exception("'storage config' is not defined in telescope_config.py")

# ...see?
CONNECTION_DATA = telescope.CONFIG['storage config']['backend']
MCONNECTION_DATA = telescope.CONFIG['storage config']

# Make the connection...
try:
    CONN = MySQLdb.connect(**CONNECTION_DATA)
except Exception, e:
    logging.exception("MySQL connection failed! Please check telescope_config.py")
    raise e

try:
    MCONN = pymongo.Connection(*MCONNECTION_DATA['connection'])[MCONNECTION_DATA['database']]
except Exception, e:
    logging.exception("MongoDB connection failed! Please check telescope_config.py")
    raise e

# Print the connection objects to stdout
logging.info("Connected to MySQL and MongoDB!")

def format_interval(intv):
    """
    Format the timedelta object represented in intv into a human-readable format.
    """
    return str(abs(intv))


def datagrab():
    """
    Run the sub-functions that actually perform the datagrab.
    """
    start = datetime.datetime.now()
    datagrab_users()
    datagrab_torrents()
    datagrab_whitelist()
    end = datetime.datetime.now()
    logging.info("Datagrab complete in %s!" % (format_interval(end - start),))


def datagrab_users():
    """
    Fetches user information from MySQL and imports it into MongoDB, overwriting any existing data.
    """
    start = datetime.datetime.now()
    c = CONN.cursor(MySQLdb.cursors.SSDictCursor)
    c.execute("SELECT ID, can_leech, torrent_pass FROM users_main WHERE Enabled='1'")
    new_users = []
    while True:
        res = c.fetchone()
        if res is None:
            break
        u = {
            'user_id': res['ID'],
            'can_leech': True if res['can_leech'] == 1 else False,
            '_id': res['torrent_pass']
        }
        new_users.append(u)
    MCONN.users.remove()
    MCONN.users.insert(new_users)
    end = datetime.datetime.now()
    logging.info("User data-grab completed in %s." % (format_interval(end - start),))
    c.close()


def datagrab_torrents():
    """
    Fetches torrent information from MySQL and imports it into MongoDB, merging with existing data.
    """
    start = datetime.datetime.now()
    c = CONN.cursor(MySQLdb.cursors.SSDictCursor)
    c.execute("SELECT ID, info_hash, freetorrent, snatched FROM torrents ORDER BY ID")
    new_torrents = []
    while True:
        res = c.fetchone()
        if res is None:
            break
        t = MCONN.torrents.find_one({"_id": res['info_hash'].encode('hex')})
        if t is not None:
            new = False
        else:
            t = {}
            new = True
            #print "%s is %s" % (res['info_hash'].encode('hex'), 'new' if new else 'not new')
        t['torrent_id'] = res['ID']
        t['freetorrent'] = True if res['freetorrent'] == 1 else False
        t['snatched'] = res['snatched']
        if new:
            t['info_hash'] = pymongo.binary.Binary(res['info_hash'])
            t['last_flushed'] = datetime.datetime.fromtimestamp(0)
            t['_id'] = res['info_hash'].encode('hex')
            t['last_seeded'] = 0
            t['balance'] = 0
            t['completed'] = 0
            t['peers'] = {}
            t['seeders'] = []
            t['leechers'] = []
        new_torrents.append(t)
    MCONN.torrents.remove()
    MCONN.torrents.insert(new_torrents)
    end = datetime.datetime.now()
    logging.info("Torrent data-grab completed in %s." % (format_interval(end - start),))
    c.close()


def datagrab_whitelist():
    """
    Fetches client whitelist from MySQL and imports it into MongoDB, overwriting any existing data.
    """
    start = datetime.datetime.now()
    c = CONN.cursor(MySQLdb.cursors.SSDictCursor)
    c.execute("SELECT peer_id FROM xbt_client_whitelist")
    new_whitelist = []
    while True:
        res = c.fetchone()
        if res is None:
            break
        new_whitelist.append({'peer_id': pymongo.binary.Binary(res['peer_id'])})
    MCONN.whitelist.remove()
    MCONN.whitelist.insert(new_whitelist)
    end = datetime.datetime.now()
    logging.info("Whitelist data-grab completed in %s." % (format_interval(end - start),))
    c.close()


def perform_pending():
    """
    Run the sub-functions that actually perform the pending operations.
    """
    start = datetime.datetime.now()
    c = CONN.cursor()
    perform_pending_snatch(c)
    perform_pending_user(c)
    perform_pending_torrent(c)
    perform_pending_peer(c)
    c.close()
    CONN.commit()
    end = datetime.datetime.now()
    logging.info("Pending operations completed in %s." % (format_interval(end - start),))


def perform_pending_user(c):
    """
    Updates MySQL's users_main table based upon the user_log collection in MongoDB.
    """
    start = datetime.datetime.now()
    nukeMe = []
    query = "INSERT INTO users_main(ID, Uploaded, Downloaded) VALUES (%s, %s, %s) ON DUPLICATE KEY UPDATE Uploaded=Uploaded+VALUES(Uploaded), Downloaded=Downloaded+VALUES(Downloaded)"
    ress = MCONN.user_log.find()
    qd = []
    for res in ress:
        res = Struct(**res)
        qd.append((res.user_id, res.download_change, res.upload_change))
        nukeMe.append(res._id)
    c.executemany(query, qd)
    map(lambda x: MCONN.user_log.remove(x), nukeMe)
    end = datetime.datetime.now()
    logging.info("Pending users: %d records inserted in %s." % (len(qd), format_interval(end - start)))


def perform_pending_peer(c):
    """
    Updates MySQL's xbt_files_users table based upon the peer_log collection in MongoDB.
    """
    start = datetime.datetime.now()
    nukeMe = []
    query = "INSERT INTO xbt_files_users(uid,fid,active,uploaded,downloaded,upspeed,downspeed,remaining,timespent,announced,ipa,peer_id,useragent) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) ON DUPLICATE KEY UPDATE active=VALUES(active), uploaded=VALUES(uploaded), downloaded=VALUES(downloaded), upspeed=VALUES(upspeed), downspeed=VALUES(downspeed), remaining=VALUES(remaining), timespent=VALUES(timespent), announced=VALUES(announced), peer_id=VALUES(peer_id), useragent=VALUES(useragent),mtime=UNIX_TIMESTAMP(NOW())"
    ress = MCONN.peer_log.find()
    qd = []
    for res in ress:
        res = Struct(**res)
        skyip = str(res.ip)
        clasz = socket.AF_INET if '.' in skyip else socket.AF_INET6
        if clasz == socket.AF_INET:
            ipa = ip2long(skyip)
        else:
            ipa = socket.inet_aton('0.0.0.0')
            ipa = struct.unpack('L', ipa)[0]
        qd.append((res.user_id, res.torrent_id, '1' if res.active else '0', res.uploaded, res.downloaded, res.upspeed,
                   res.downspeed, res.left, res.announcing_for, res.announces, ipa, str(res.peer_id), str(res.ua)))
        nukeMe.append(res._id)
    c.executemany(query, qd)
    map(lambda x: MCONN.peer_log.remove(x), nukeMe)
    end = datetime.datetime.now()
    logging.info("Pending peers: %d records inserted in %s." % (len(qd), format_interval(end - start)))


def perform_pending_snatch(c):
    """
    Updates MySQL's xbt_snatched table based upon the snatch_log collection in MongoDB.
    """
    start = datetime.datetime.now()
    nukeMe = []
    query = "INSERT INTO xbt_snatched(uid,fid,tstamp,IP) VALUES (%s, %s, %s, %s)"
    ress = MCONN.snatch_log.find()
    qd = []
    for res in ress:
        res = Struct(**res)
        qd.append((res.user_id, res.torrent_id, time.mktime(res.time_now.timetuple()), res.ip))
        nukeMe.append(res._id)
    c.executemany(query, qd)
    map(lambda x: MCONN.snatch_log.remove(x), nukeMe)
    end = datetime.datetime.now()
    logging.info("Pending snatches: %d records inserted in %s." % (len(qd), format_interval(end - start)))


def perform_pending_torrent(c):
    """
    Updates MySQL's torrents table based upon the torrent_log collection in MongoDB.
    """
    start = datetime.datetime.now()
    nukeMe = []
    query = "INSERT INTO torrents(ID,Seeders,Leechers,Snatched,Balance) VALUES (%s,%s,%s,%s,%s)  ON DUPLICATE KEY UPDATE Seeders=VALUES(Seeders), Leechers=VALUES(Leechers), Snatched=Snatched+VALUES(Snatched), Balance=VALUES(Balance), last_action = IF(VALUES(Seeders) > 0, NOW(), last_action)"
    ress = MCONN.torrent_log.find()
    qd = []
    for res in ress:
        res = Struct(**res)
        qd.append((int(res.torrent_id), res.seeders, res.leechers, 1 if res.snatched else 0, res.balance))
        nukeMe.append(res._id)
    c.executemany(query, qd)
    map(lambda x: MCONN.torrent_log.remove(x), nukeMe)
    end = datetime.datetime.now()
    logging.info("Pending torrents: %d records inserted in %s." % (len(qd), format_interval(end - start)))


def perform_hedgetrimming():
    """
    Culls peers which are older than 1 hour from torrents.

    1 hour definition is stored in the MAP_REDUCER JavaScript function defined above.
    """
    start = datetime.datetime.now()
    resCol = MCONN.torrents.map_reduce(MAP_REDUCER, REDUCER, 'trimming_tmp')
    resF = resCol.find()
    pruneCount = 0
    prunedTorrents = 0
    for res in resF:
        prunedTorrents += 1
        tid = res['_id']
        for pid, blarp in res['value'].iteritems():
            pruneCount += 1
            MCONN.torrents.update({'_id': tid},
                    {"$unset": {"peers.%s" % (pid,): 1}, "$pull": {"seeders": pid, "leechers": pid}})
    end = datetime.datetime.now()
    logging.info("Pruned %d peers from %d torrents in %s." % (pruneCount, prunedTorrents, format_interval(end - start)))


logging.info("Performing start-up datagrab")
datagrab()

i = 0

while True:
    time.sleep(10)
    if i > 20:
        i = 0
        logging.info("Performing datagrab")
        datagrab()
        logging.info("Running pending actions")
        perform_pending()
        logging.info("Performing peer cull")
        perform_hedgetrimming()
    else:
        logging.info("Running pending actions")
        logging.debug("%d seconds until full run" % ((20 - i) * 10))
        perform_pending()
        i += 1




