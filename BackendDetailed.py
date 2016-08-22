import Backend
import datetime, pytz
import HumanTime
import OsmDiff as osmdiff
import OsmChangeset as oc

class Backend(Backend.Backend):
    def __init__(self, config, subcfg):
        super(Backend, self).__init__(config, subcfg)
        self.print_meta = getattr(subcfg, 'print_meta', False)

    def print_state(self, db):
        strfmt = '%Y:%m:%d %H:%M:%S'
        #time1 = state.first_timestamp.strftime(strfmt)
        #time2 = state.timestamp.strftime(strfmt)
        #print('Tracked period: {} - {} UTC.  {} changesets.'.format(time1, time2, len(state.area_chgsets)))
        self.print_chgsets(db, self.print_meta)

    def print_chgsets(self, db, print_meta=False):
        for c in db.chgsets_find(state=[db.STATE_CLOSED, db.STATE_OPEN, db.STATE_ANALYZING2,
                                        db.STATE_REANALYZING, db.STATE_DONE]):
            cid = c['cid']
            meta = db.chgset_get_meta(cid)
            info = db.chgset_get_info(cid)
            #print 'cset=', pprint.pprint(data)
            if 'comment' in meta['tag'].keys():
                comment = meta['tag']['comment']
            else:
                comment = '-no comment-'
            if 'source' in meta['tag'].keys():
                source = "source='"+meta['tag']['source']+"'"
            else:
                source = ''
            timestamp = oc.Changeset.get_timestamp(meta)[1]
            htimestamp = HumanTime.date2human(timestamp)
            print u"  {} \'{}\' {} ('{}') '{}' state={}".format(cid, meta['user'], htimestamp, timestamp, comment, info['state']).encode('ascii','backslashreplace')
            if print_meta:
                for k,v in meta.items():
                    print u' {0}:{1}'.format(k,v).encode('ascii','backslashreplace'),
                for k,v in meta.get('tags',{}).items():
                    print u' {0}:{1}'.format(k,v).encode('ascii','backslashreplace'),
                print
