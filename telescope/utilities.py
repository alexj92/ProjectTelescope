"""
This file defines various decorators and functions used by the ProjectTelescope handler.
"""

from telescope.errors import *
from telescope.models import Peer
import bottle
import telescope

STORAGE = telescope.STORAGE

def fail(reason):
    """
    Causes bottle to return a bencoded failure message.

    To modify the failure messages, modify errors.py
    """
    failcode = 900
    if isinstance(reason, ( int, long )):
        if reason in REASONS_CODE.keys():
            failcode = REASONS_CODE[reason]
        reason = REASONS[reason]
    else:
        reason = str(reason)
    raise bottle.HTTPResponse("d14:failure reason%d:%s12:failure codei%dee" % (len(reason), reason, failcode),
                              header={'Content-type': 'text/plain'})


def check_key(cb):
    """
    Decorator for taking a request key and looking up a user
    """

    def funcn(*args, **kwargs):
        if 'key' not in kwargs:
            fail(REASON_NO_PASSKEY)
        key = kwargs['key']
        del kwargs['key']
        kwargs['user'] = STORAGE.lookup_user(key)
        if kwargs['user'].is_anonymous:
            fail(REASON_BAD_PASSKEY)
        return cb(*args, **kwargs)

    return funcn


def required_params(arra):
    """
    Decorator for requiring parameters in bottle.request.query and returning a bencoded failure response otherwise
    """
    SPECIAL_CHECK = {
        'info_hash': REASON_REQUEST_NO_INFO_HASH,
        'peer_id': REASON_REQUEST_NO_PEER_ID,
        'port': REASON_REQUEST_NO_PORT,
        }

    def wrap_funcn(cb):
        def funcn(*args, **kwargs):
            availablekeys = bottle.request.query.keys()
            for checkkey in arra:
                if not checkkey in availablekeys:
                    if checkkey in SPECIAL_CHECK.keys():
                        fail(SPECIAL_CHECK[checkkey])
                    fail(REASON_REQUEST_ERROR)
            return cb(*args, **kwargs)

        return funcn

    return wrap_funcn


def check_params(arra):
    """
    Decorator for checking a subset of parameters in bottle.request.query and returning a bencoded failure response otherwise
    """
    SPECIAL_CHECK = {
        'info_hash': REASON_REQUEST_BAD_INFO_HASH,
        'peer_id': REASON_REQUEST_BAD_PEER_ID,
        'numwant': REASON_REQUEST_BAD_NUMWANT,
        }

    def wrap_funcn(cb):
        def funcn(*args, **kwargs):
            for checkkey in arra:
                if not checkkey in bottle.request.query.keys():
                    continue

                if not _check_params_do(checkkey, bottle.request.query[checkkey]):
                    if checkkey in SPECIAL_CHECK.keys():
                        fail(SPECIAL_CHECK[checkkey])
                    fail(REASON_REQUEST_ERROR)
            return cb(*args, **kwargs)

        return funcn

    return wrap_funcn


def _check_params_do(name, val):
    """
    Actually performs the checking mentioned in check_params
    """
    if name == 'info_hash':
        return len(val) == 20
    elif name == 'peer_id':
        return len(val) == 20 and STORAGE.check_peer(val)
    elif name == 'numwant':
        return int(val) < 250
    fail(REASON_REQUEST_ERROR)


def conjure_peer(inp):
    """
    Make a Peer out of dict provided. If a Peer is passed, return it.
    """
    if isinstance(inp, Peer):
        return inp
    else:
        return Peer(**inp)
        
