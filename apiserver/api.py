#!/usr/bin/env python

import datetime, pytz
import connexion
from connexion import NoContent
import logging, logging.config

logger = logging.getLogger('osmtracker-api')

def get_changesets(limit, state=None):
    csets = []
    for c in app.db.chgsets_find(state=state):
        logger.debug('cset={}'.format(c))
        cpykeys = ['cid', 'state', 'labels', 'queued', 'updated', 'refreshed',
                   'state_changed', 'source' ]
        cset = { 'updated': c['updated'].isoformat() }
        for k in cpykeys:
            if k in c:
                if type(c[k]) is datetime.datetime:
                    cset[k] = c[k].isoformat()
                else:
                    cset[k] = c[k]
        csets.append(cset)
        if limit>0 and len(csets)>=limit:
            break
    logger.debug('changesets={}'.format(csets))
    return {'changesets': csets,
            'timestamp': datetime.datetime.utcnow().replace(tzinfo=pytz.utc).isoformat()}

def get_changeset(cset_id):
    csets = app.db.chgsets_find(cid=cset_id, state=None)
    if csets:
        for c in csets:
            return c
    else:
        return NoContent, 404

def get_pointer():
    return NoContent, 404
