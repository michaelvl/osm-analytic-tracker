import datetime, pytz
import HumanTime
import OsmDiff as osmdiff
import OsmChangeset as oc
import pprint

class Backend(object):
    def __init__(self, config, subcfg):
        self.debug = False
        self.generation = None
        self.config = config
        self.subcfg = subcfg

    def print_state(self, state):
        time = state.generation_timestamp.strftime('%Y:%m:%d %H:%M:%S')
        print 'Generation {} @ {}'.format(state.generation, time)
        if self.generation != state.generation:
            self.generation = state.generation

            self.print_chgsets(state.area_chgsets,
                               state.area_chgsets_info)

    def print_chgsets(self, csets, chginfo, print_tags=False):
        for chgid in csets[::-1]:
            meta = chginfo[chgid]['meta']
            #print '>>cset=', pprint.pprint(meta)
            #print '>>tagdiff=', pprint.pprint(chginfo[chgid]['tagdiff'])
            #print '>>other_users=', pprint.pprint(chginfo[chgid]['other_users'])
            if 'comment' in meta['tag'].keys():
                comment = meta['tag']['comment']
            else:
                comment = '-no comment-'
            if 'source' in meta['tag'].keys():
                source = 'source=\''+meta['tag']['source']+'\''
            else:
                source = ''
            (tstype, timestamp) = oc.Changeset.get_timestamp(meta)
            htimestamp = HumanTime.date2human(timestamp)
            print u'  {0} \'{1}\' {2} (\'{3}\') \'{4}\' {5}'.format(chgid, meta['user'], htimestamp, timestamp, comment, source)
            if print_tags:
                pprint.pprint(chginfo['other_users'])
                pprint.pprint(chginfo['summary'])
                pprint.pprint(chginfo['tagdiff'])
                pprint.pprint(chginfo['source'])

    def _pluS(self, num):
        '''Return plural s'''
        if num==1:
            return ''
        return 's'

    def _i2s(self, num):
        '''Int to string using human rounding'''
        ss = str(num)
        txt = None
        if len(ss) <=8:
            for pp in range(0, len(ss), 3):
                if txt:
                    txt = ss[-3:]+','+txt
                else:
                    txt = ss[-3:]
                ss = ss[:-3]
        else:
            txt = str(num) # TODO: Better rounding for large numbers
        return txt

    def merge_int_dict(self, a, b):
        '''Recursively merge dictionaries where values are either numbers or other dicts'''
        for k,v in b.iteritems():
            if type(v) is int or type(v) is float:
                a[k] = a.get(k, 0)+v
            else:
                a[k] = self.merge_int_dict(a.get(k, dict()), v)
        return a
