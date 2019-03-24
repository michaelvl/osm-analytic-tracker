import datetime, pytz
import ColourScheme as col
import logging

logger = logging.getLogger(__name__)

def check(cset, meta, info):
    cid = cset['cid']
    if not meta:
        # Dummy data
        meta = {'open': False, 'comments_count': 0}
    if not info or 'summary' not in info:
        logger.error('Invalid info for cid {}: {}'.format(cid, cset))
        # Dummy data
        if cset and 'updated' in cset:
            ts = cset['updated']
        else:
            ts = datetime.datetime.now()
        colours = col.ColourScheme(seed=0)
        if 'user' in cset:
            col = colours.get_colour(cset['user'])
        else:
            col = colours.get_colour('anonymous')
        info = {'state': '-', 'misc':{'state': '', 'timestamp': ts, 'timestamp_type_txt': '', 'user_colour': col},
                'summary': {'create' : { 'node': 0, 'way':0, 'relation':0, 'relation_tags':{}},
                            'modify' : { 'node': 0, 'way':0, 'relation':0, 'relation_tags':{}},
                            'delete' : { 'node': 0, 'way':0, 'relation':0, 'relation_tags':{}},
                            '_create':0, '_modify':0, '_delete':0},
                'tags': {},
                'tagdiff': {'create':{}, 'delete':{}, 'modify':{}},
                'simple_nodes': {'create':0, 'modify':0, 'delete':0},
                'other_users': {},
                'mileage_m': {'_navigable_create':0, '_navigable_delete':0, '_all_create':0, '_all_delete':0, 'by_type': {}},
                'geometry': {'node': {}, 'way':{}, 'relation':{}}
        }
    return meta, info
