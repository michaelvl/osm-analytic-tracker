import Backend
import datetime, pytz
import HumanTime
import OsmDiff as osmdiff
import OsmChangeset as oc

class Backend(Backend.Backend):
    def __init__(self, config, subcfg):
        super(Backend, self).__init__(config, subcfg)
        self.print_meta = getattr(subcfg, 'print_meta', False)

    def print_state(self, state):
        strfmt = '%Y:%m:%d %H:%M:%S'
        time1 = state.first_timestamp.strftime(strfmt)
        time2 = state.timestamp.strftime(strfmt)
        print('Tracked period: {} - {} UTC'.format(time1, time2))
        self.print_chgsets(state, self.print_meta)

    def print_chgsets(self, state, print_meta=False):
        csets = state.area_chgsets
        chginfo = state.area_chgsets_info
        for chgid in csets[::-1]:
            meta = chginfo[chgid]['meta']
            #print 'cset=', pprint.pprint(data)
            if 'comment' in meta['tag'].keys():
                comment = meta['tag']['comment']
            else:
                comment = '-no comment-'
            if 'source' in meta['tag'].keys():
                source = 'source=\''+meta['tag']['source']+'\''
            else:
                source = ''
            timestamp = oc.Changeset.get_timestamp(meta)[1]
            htimestamp = HumanTime.date2human(timestamp)
            print u'  {0} \'{1}\' {2} (\'{3}\') \'{4}\' {5}'.format(chgid, meta['user'], htimestamp, timestamp, comment, source)
            if print_meta:
                for k,v in meta.items():
                    print u' {0}:{1}'.format(k,v),
                for k,v in meta.get('tags',{}).items():
                    print u' {0}:{1}'.format(k,v),
                print
