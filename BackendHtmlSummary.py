from __future__ import print_function
import BackendHtml
import datetime, pytz
import HumanTime
import OsmDiff as osmdiff
import OsmChangeset as oc
import ColourScheme as col
import operator
import logging

logger = logging.getLogger(__name__)

class Backend(BackendHtml.Backend):
    def __init__(self, config):
        super(Backend, self).__init__(config)
        self.list_fname = config.getpath('path', 'BackendHtmlSummary')+config.get('filename', 'BackendHtmlSummary')
        self.js_timestamp_fmt = '%a, %d %b %Y %H:%M:%S %Z'
        self.generation = None

        #self.start_page(self.list_fname)
        self.print_state()
        #self.end_page()

    def print_state(self, state=None):
        force = True
        if not state or self.generation != state.generation or force:
            self.start_page(self.list_fname)
            if not state:
                self.pprint('Nothing here yet')
            else:
                self.generation = state.generation
                csets = state.area_chgsets
                info = state.area_chgsets_info

                strfmt = '%Y:%m:%d %H:%M:%S'

                now = datetime.datetime.utcnow().replace(tzinfo=pytz.utc)
                self.start_list('summary')
                time1 = state.first_timestamp.strftime(strfmt)
                #time2 = datetime.datetime.now().strftime(strfmt)
                time2 = state.timestamp.strftime(strfmt)
                self.item('Tracked period: {} - {} UTC'.format(time1, time2))
                tracked_hours = (state.timestamp-state.first_timestamp).total_seconds()/3600

                if state.area_chgsets:
                    first_cset = state.area_chgsets[0]
                    first_cset_ts = oc.Changeset.get_timestamp(state.area_chgsets_info[first_cset]['meta'])[1]
                    cset_tracked_hours = (state.timestamp-first_cset_ts).total_seconds()/3600
                    self.item('Changeset period: {} - {} UTC'.format(first_cset_ts.strftime(strfmt), time2))
                    logger.debug('Changeset period: {} - {} UTC'.format(first_cset_ts.strftime(strfmt), time2))

                users = {}
                notes = 0
                for chgid in csets:
                    meta = info[chgid]['meta']
                    user = meta['user']
                    users[user] = users.get(user,0) + 1
                    notes += int(meta['comments_count'])

                # Summarize edits and mileage - we don't do this incrementally
                # since csets can be split over multiple diffs
                edits = {'node':     {'create':0, 'modify':0, 'delete':0},
                         'way':      {'create':0, 'modify':0, 'delete':0},
                         'relation': {'create':0, 'modify':0, 'delete':0}}
                mileage = {}
                for chgid in csets[::-1]:
                    summary = info[chgid]['summary']
                    for action in ['create', 'modify', 'delete']:
                        if summary['_'+action] > 0:
                            for type in ['node', 'way', 'relation']:
                                edits[type][action] += summary[action][type]
                    self.merge_int_dict(mileage, info[chgid]['mileage'])

                self.item('<img src=node.png> Nodes created: {} modified: {} deleted: {}'.format(edits['node']['create'],edits['node']['modify'],edits['node']['delete']))
                self.item('<img src=way.png> Ways created: {} modified: {} deleted: {}'.format(edits['way']['create'],edits['way']['modify'],edits['way']['delete']))
                self.item('<img src=relation.png> Relations created: {} modified: {} deleted: {}'.format(edits['relation']['create'],edits['relation']['modify'],edits['relation']['delete']))
                self.item('<img src=note.png> Notes: {}'.format(notes))

                if mileage:
                    sum = 0
                    num_items = 0
                    self.item('Mileage:')
                    self.start_list(lclass='sum-list')
                    by_type = mileage['by_type']
                    for cat in by_type.keys():
                        mi = [(t,int(by_type[cat][t])) for t in by_type[cat].keys()]
                        mi = sorted(mi, key=lambda x: x[1], reverse=True)
                        for typ,m in mi:
                            if num_items < 13:
                                self.item('{}={}: {} meters'.format(cat, typ, self._i2s(m)))
                            sum += m
                            num_items += 1
                    if cset_tracked_hours>0:
                        self.item('Total navigable: {} meters ({}m/hour)'.format(self._i2s(sum), self._i2s(int(sum/cset_tracked_hours))))
                    self.end_list()

                txt_users = 'users'
                txt_cset = 'changesets'
                if len(users) == 1:
                    txt_users = 'user'
                if len(csets) == 1:
                    txt_cset = 'changeset'
                self.item('{} {} by {} {}'.format(len(csets), txt_cset, len(users), txt_users))
                self.end_list()

                if hasattr(state, 'pointer'):
                    lag = now-state.pointer.timestamp()
                    self.pprint('<div id="lag">Lag: {}s</div>'.format(int(lag.seconds)))
                self.pprint('<div id="sequence_numbers">Diff sequence numbers: {} - {}</div>'.format(state.first_seqno, state.latest_seqno))
                self.pprint('<div id="generation">Generation '+str(state.generation)+'</div>')
                self.pprint('<div id="summary_created">'+now.strftime(self.js_timestamp_fmt)+'</div>')
            self.end_page()
