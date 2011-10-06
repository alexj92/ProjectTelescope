import pymongo
import struct, socket
import time
import pymongo.binary, pymongo.code
import MySQLdb
import MySQLdb.cursors
import datetime

class Struct:
    def __init__(self, **entries): 
        self.__dict__.update(entries)


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
        quads = quads[:-1] + [0,] * (4 - len(quads)) + host

    lngip = 0
    for q in quads:
        lngip = (lngip << 8) | int(q)
    return lngip

import telescope
CONNECTION_DATA = telescope.CONFIG['storage config']['backend']
MCONNECTION_DATA = telescope.CONFIG['storage config']

#CONNECTION_DATA['cursorclass'] = MySQLdb.cursors.SSDictCursor

CONN = MySQLdb.connect(**CONNECTION_DATA)
MCONN = pymongo.Connection(*MCONNECTION_DATA['connection'])[MCONNECTION_DATA['database']]

print CONN
print MCONN


def datagrab():
    datagrab_users()
    datagrab_torrents()
    datagrab_whitelist()
    print "datagrab done! doing pendings..."
    perform_pending()

def datagrab_users():
    c = CONN.cursor(MySQLdb.cursors.SSDictCursor)
    c.execute("SELECT ID, can_leech, torrent_pass FROM users_main WHERE Enabled='1'")
    new_users = []
    while True:
       res = c.fetchone()
       if res is None:
           break
       u = {}
       u['user_id'] = res['ID']
       u['can_leech'] = True if res['can_leech'] == 1 else False
       u['_id'] = res['torrent_pass']
       new_users.append(u)
    MCONN.users.remove()
    MCONN.users.insert(new_users)
    print "DONE!"
    c.close()

def datagrab_torrents():
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
    print "DONE!"
    c.close()

def datagrab_whitelist():
    c = CONN.cursor(MySQLdb.cursors.SSDictCursor)
    c.execute("SELECT peer_id FROM xbt_client_whitelist")
    new_whitelist = []
    while True:
        res = c.fetchone()
        if res is None:
            break
        new_whitelist.append({'peer_id': res['peer_id']})
    MCONN.whitelist.remove()
    MCONN.whitelist.insert(new_whitelist)
    print "Done!"
    c.close()

def perform_pending():
    c = CONN.cursor()
    perform_pending_snatch(c)
    perform_pending_user(c)
    perform_pending_torrent(c)
    perform_pending_peer(c)
    c.close()
    CONN.commit()

def perform_pending_user(c):
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
    print "Pending users: %d records inserted" % (len(qd,))

def perform_pending_peer(c):
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
        qd.append((res.user_id, res.torrent_id, '1' if res.active else '0', res.uploaded, res.downloaded, res.upspeed, res.downspeed, res.left, res.announcing_for, res.announces, ipa, str(res.peer_id), str(res.ua)))
        nukeMe.append(res._id)
    c.executemany(query, qd)
    map(lambda x: MCONN.peer_log.remove(x), nukeMe)
    print "Pending peers: %d records inserted" % (len(qd,))

def perform_pending_snatch(c):
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
    print "Pending snatches: %d records inserted" % (len(qd,))

def perform_pending_torrent(c):
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
    print "Pending torrents: %d records inserted" % (len(qd,))

def perform_hedgetrimming():
    resCol = MCONN.torrents.map_reduce(MAP_REDUCER, REDUCER, 'trimming_tmp')
    resF = resCol.find()
    pruneCount = 0
    prunedTorrents = 0
    for res in resF:
        prunedTorrents += 1
        tid = res['_id']
        for pid, blarp in res['value'].iteritems():
            pruneCount += 1
            MCONN.torrents.update({ '_id': tid }, { "$unset": { "peers.%s" % (pid,): 1 }, "$pull": { "seeders": pid, "leechers": pid } })
    print "Pruned %d peers from %d torrents" % (pruneCount, prunedTorrents)
    

print "Here goes..."
print "FIRST TIME DATA GRAB!"
datagrab()

i = 0

while True:
    time.sleep(10)
    if i > 20:
        i = 0
        datagrab()
        print "Now doing some hedgetrimming"
        perform_hedgetrimming()
    else:
        i += 1
        perform_pending()




