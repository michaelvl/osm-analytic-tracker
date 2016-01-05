# -*- coding: utf-8 -*-

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

    def __init__(self, config, subcfg):
        super(Backend, self).__init__(config, subcfg)
        self.list_fname = config.getpath('path', 'BackendHtmlSummary')+subcfg['filename']
        self.template_name = subcfg['template']
        self.generation = None
        self.print_state()

    def print_state(self, state=None):
        force = True # Because otherwise 'summary_created' timestamp below is not updated
        if not state or self.generation != state.generation or force:
            self.start_page(self.list_fname)
            if not state:
                self.pprint('Nothing here yet')
            else:
                template = state.env.get_template(self.template_name)
                self.generation = state.generation
                csets = state.area_chgsets
                info = state.area_chgsets_info
                now = datetime.datetime.utcnow().replace(tzinfo=pytz.utc)
                data = {
                    'state':             state,
                    'track_starttime':   state.first_timestamp,
                    'track_endtime':     state.timestamp,
                    'tracked_hours':     (state.timestamp-state.first_timestamp).total_seconds()/3600,
                    'summary_created':   now,
                    'pointer_timestamp': state.pointer.timestamp()
                }
                cset_tracked_hours = 0
                if state.area_chgsets:
                    first_cset = state.area_chgsets[0]
                    first_cset_ts = oc.Changeset.get_timestamp(state.area_chgsets_info[first_cset]['meta'])[1]
                    cset_tracked_hours = (state.timestamp-first_cset_ts).total_seconds()/3600
                    data['cset_first'] = first_cset_ts

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
                    self.merge_int_dict(mileage, info[chgid]['mileage_m'])
                data['edits'] = edits
                data['users'] = users
                data['notes'] = notes
                data['csets'] = csets

                mileage_bytype = []
                if mileage:
                    sum = 0
                    num_items = 0
                    by_type = mileage['by_type']
                    for cat in by_type.keys():
                        mi = [(t,int(by_type[cat][t])) for t in by_type[cat].keys()]
                        mi = sorted(mi, key=lambda x: x[1], reverse=True)
                        for typ,m in mi:
                            if num_items < 13:
                                mileage_bytype.append((cat, typ, self._i2s(m)))
                            sum += m
                            num_items += 1
                    data['mileage_bytype'] = mileage_bytype
                    if cset_tracked_hours>0:
                        data['mileage_meter'] = self._i2s(sum)
                        data['mileage_meter_per_hour'] = self._i2s(int(sum/cset_tracked_hours))

                if hasattr(state, 'pointer'):
                    lag = now-state.pointer.timestamp()
                    data['lag_seconds'] = int(lag.seconds)

                logger.debug('Data passed to template: {}'.format(data))
                self.pprint(template.render(data))
            self.end_page()
