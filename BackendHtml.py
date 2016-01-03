from __future__ import print_function
import Backend
import datetime, pytz
import HumanTime
import OsmDiff as osmdiff
import OsmChangeset as oc
import ColourScheme as col
import operator
import os
import logging

logger = logging.getLogger(__name__)

class Backend(Backend.Backend):
    def __init__(self, config):
        super(Backend, self).__init__(config)
        self.list_fname = config.getpath('path', 'BackendHtml')+config.get('filename', 'BackendHtml')
        self.list_fname_old = config.getpath('path', 'BackendHtml')+config.get('filename_old', 'BackendHtml')
        self.js_timestamp_fmt = '%a, %d %b %Y %H:%M:%S %Z'
        self.colours = col.ColourScheme()

        self.generation = None
        self.last_chg_seen = None
        self.last_update = datetime.datetime.now()

        self.start_page(self.list_fname)
        self.no_items()
        self.end_page()

    def print_state(self, state):
        now = datetime.datetime.now()
        #if now.day != self.last_update.day:
        #    print('Cycler - new day: {} {}'.format(now.day, self.last_update.day))
        #period = now-state.cset_start_time
        #if period.total_seconds() > self.config.get('horizon_hours', 'tracker')*3600:
        #    os.rename(self.list_fname, self.list_fname_old)
        #    print('Cycler')
        #    state.clear_csets()
        self.last_update = datetime.datetime.now()
        if self.generation != state.generation:
            self.generation = state.generation

            self.start_page(self.list_fname)
            self.print_chgsets(state)
            self.end_page()

    def pprint(self, txt):
        print(txt.encode('utf8'), file=self.f)
        #print('*'+txt)

    def start_page(self, fname):
        self.f = open(fname, 'w', os.O_TRUNC)
        self.pprint('<!-- Generated by OpenStreetMap Analytic Difference Engine -->')

    def end_page(self):
        self.f.close()
        self.f = None

    def start_list(self, lclass=None, xtra=''):
        if lclass:
            self.pprint('<ul class="'+lclass+'" '+xtra+'>')
        else:
            self.pprint('<ul '+xtra+'>')

    def end_list(self):
        self.pprint('</ul>')

    def start_cset(self, cset_info, user, cset_id, timestamp, timestamp_type, comment, ctype='cset'):
        if not comment:
            comment = 'Changeset '+str(cset_id)
        colour = 'background-color: #'+self.colours.get_colour(user)
        #ts = timestamp.strftime('%Y-%m-%d %H:%MZ')
        ts = timestamp.strftime(self.js_timestamp_fmt)
        logger.debug(u'cset {} - {}'.format(cset_id, comment))
        self.pprint('<li class="'+ctype+'" data-timestamp="'+ts+'" data-timestamp_type="'+timestamp_type+'">'
                    #+'<div class="csethead">'
                    +'<ul class="csethead">'
                    +'<li>'
                    +'<div class="legend" style="'+colour+'">&#8203;</div>'
                    +'<div class="user"><a href="http://www.openstreetmap.org/user/'+user+'">'+user+'</a></div>'
                    +'<div class="changeset"><a href="http://www.openstreetmap.org/changeset/'+str(cset_id)+'">'+comment+'</a></div>'
                    +'<div class="changeset-source">'+str(cset_info['source'])+'</div>'
                    +'</li>')
                    # TODO: Change below to use item()
                    # +'<div class="legend" style="'+colour+'">&#8203;</div>'
                    # +'<div class="user"><a href="http://www.openstreetmap.org/user/'+user+'">'+user+'</a></div>'
                    # +'<div class="changeset"><a href="http://www.openstreetmap.org/changeset/'+str(cset_id)+'">'+comment+'</a></div>')

    def end_cset(self):
        pass

    def start_cset_body(self):
        self.pprint('</ul>')
        #self.pprint('</div>')
        self.pprint('<ul class="details">')
        #self.pprint('<div class"details">')

    def item(self, k, v=None, dclass=None, hclass=None):
        if dclass:
            divstart = u'<div class="'+dclass+'">'
        else:
            divstart = u'<div>'
        txt = divstart+u'{}</div>'.format(k)
        if v:
            txt += u'<div>{}</div>'.format(v)
        if hclass:
            self.pprint('<li class="'+hclass+'">'+txt+'</li>')
        else:
            self.pprint('<li>'+txt+'</li>')

    def items(self, k, v=None, dclass=None, hclass=None, dclasses=None):
        if dclass:
            divstart = u'<div class="'+dclass+'">'
        else:
            divstart = u'<div>'
        txt = divstart+u'{}</div>'.format(k)
        if dclasses:
            for vv,hcl in zip(v,dclasses):
                txt += u'<div class="{}">{}</div>'.format(hcl,vv)
        else:
            for vv in v:
                txt += u'<div>{}</div>'.format(vv)
        if hclass:
            self.pprint('<li class="'+hclass+'">'+txt+'</li>')
        else:
            self.pprint('<li>'+txt+'</li>')

    def items_end(self):
        self.pprint('</ul>')
        #self.pprint('</div>')

    def no_items(self, state=None):
        if state:
            time = state.timestamp.strftime('%Y:%m:%d %H:%M:%S')
        else:
            time = datetime.datetime.utcnow().replace(tzinfo=pytz.utc)
            time = time.strftime('%Y:%m:%d %H:%M:%S')
        self.pprint('<p>No changesets at '+time+' (UTC)</p>')

    def print_chgsets(self, state):
        csets = state.area_chgsets
        chginfo = state.area_chgsets_info
        self.start_list()
        for chgid in csets[::-1]:
            meta = chginfo[chgid]['meta']
            summ = chginfo[chgid]['summary']
            ctype = 'cset'
            is_new = chgid in state.chgsets_new
            if is_new:
                ctype += ' new'
            #print 'cset=', pprint.pprint(data)
            if 'comment' in meta['tag'].keys():
                comment = meta['tag']['comment']
            else:
                comment = None
            if 'source' in meta['tag'].keys():
                source = 'source=\''+meta['tag']['source']+'\''
            else:
                source = None
            if 'imagery_used' in meta['tag'].keys():
                imagery = 'imagery_used=\''+meta['tag']['imagery_used']+'\''
            else:
                imagery = None
            (tstype, timestamp) = oc.Changeset.get_timestamp(meta)
            user = meta['user']
            ts_type2txt = { 'created_at': 'Started', 'closed_at': 'Closed' }

            # TODO: source, imagery?
            if 'bot' in meta['tag'].keys() and meta['tag']['bot'] == 'yes':
                ctype += ' bot'

            self.start_cset(chginfo[chgid], user, chgid, timestamp, ts_type2txt[tstype], comment, ctype)

            if not comment:
                link = '<a href="http://wiki.openstreetmap.org/wiki/Good_changeset_comments">{}</a>'
                self.item(link.format('No comment'), dclass='warning')
            #if not ('source' in meta['tag'].keys() or 'imagery_used' in meta['tag'].keys()):
            if not (source or imagery):
                link = '<a href="http://wiki.openstreetmap.org/wiki/Changeset">{}</a>'
                self.item(link.format('No source attribute'), dclass='warning')
            if ('type = route' in summ['create']['relation_tags'].keys() or
                'type = route' in summ['modify']['relation_tags'].keys() or
                'type = route' in summ['delete']['relation_tags'].keys()):
                self.item('Modifies route relation', dclass='warning')
            if meta['comments_count'] > 0:
                self.item('Has comments', dclass='warning')

            notes = int(meta['comments_count'])
            if notes > 0:
                self.item('{} note{}'.format(notes, self._pluS(int(notes))))

            link = '<a href="/osm/diffmap.php?cid={}">VisualDiff</a>'
            self.item(link.format(chgid))

            self.start_cset_body()

            conv = {'create': 'Added:', 'delete': 'Deleted:', 'modify' : 'Modified:'}
            for action in ['create', 'modify', 'delete']:
                if summ['_'+action] > 0:
                    counts = []
                    dclasses = []
                    for type in ['node', 'way', 'relation']:
                        counts.append(summ[action][type])
                        dclasses.append(type+'_'+action)
                    self.items(conv[action], counts, hclass='action_'+action, dclasses=dclasses)

            pn = chginfo[chgid]['simple_nodes']
            if pn['create'] or pn['modify'] or pn['delete']:
                self.items('Simple nodes:', [pn['create'], pn['modify'],  pn['delete']],
                           dclasses=['simplenodes_create','simplenodes_modify','simplenodes_delete'])

            
            mileage = chginfo[chgid]['mileage_m']
            if mileage['_navigable_create'] or mileage['_navigable_delete']:
                self.items('Navigable meters:', [int(mileage['_navigable_create']), int(mileage['_navigable_delete'])],
                           dclasses=['navigable_create', 'navigable_delete'])

            tagdiff = chginfo[chgid]['tagdiff']
            count = 0
            max_len = 20
            for action in ['create', 'modify', 'delete']:
                sorted_tags = sorted(tagdiff[action].items(), key=operator.itemgetter(1), reverse=True)
                for k,v in sorted_tags:
                    self.item(k, v, hclass='action_'+action)
                    count += 1
                    if count == max_len<len(sorted_tags): # Max tags allowed
                        num = len(sorted_tags)-max_len
                        self.item('{} other item{}'.format(num, self._pluS(num)), dclass='trailer')
                        break

            #ousr = sorted(chginfo[chgid]['other_users'].items(), key=operator.itemgetter(1), reverse=True)
            ousr = chginfo[chgid]['other_users']
            count = 0
            max_len = 5
            for k,v in ousr.iteritems(): # k is uid
                if k==0:
                    user = '(Anonymous)'
                    url = '<a href="http://wiki.openstreetmap.org/wiki/Anonymous_edits">'+user+'</a>'
                else:
                    user = v['user']
                    url = u'<a href="http://www.openstreetmap.org/user/'+user+'">'+user+'</a>'
                if count==0:
                    txt = u"Affects edits by {}{}".format(url,',' if len(ousr)>1 else '')
                else:
                    txt = u"{}{}".format(url,',' if len(ousr)>(count+1) else '')
                self.item(txt, dclass='trailer')
                count += 1
                if count == max_len<len(ousr):
                    num = len(ousr)-max_len
                    self.item('{} more user{}'.format(num, self._pluS(num)), dclass='trailer')
                    break

            #if meta['comments_count'] > 0:
            #    self.item(u'Notes:', dclass='trailer')
            #    for c in meta['discussion']:
            #        self.item(u'{}'.format(c['text']), dclass='trailer')

            self.items_end()
            self.end_cset()
        self.end_list()
        if len(csets) > 0:
            print('last seen {} next is {}'.format(self.last_chg_seen, csets[-1]))
            self.last_chg_seen = csets[-1]
        logger.debug('id of state is {}'.format(id(state)))
