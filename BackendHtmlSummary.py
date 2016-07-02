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
import jinja2

logger = logging.getLogger(__name__)

class Backend(BackendHtml.Backend):

    def __init__(self, config, subcfg):
        super(Backend, self).__init__(config, subcfg)
        self.list_fname = config.getpath('path', 'BackendHtmlSummary')+'/'+subcfg['filename']
        self.template_name = subcfg['template']
        self.env = jinja2.Environment(loader=jinja2.FileSystemLoader(config.getpath('template_path', 'tracker')))
        self.env.filters['js_datetime'] = self._js_datetime_filter
        self.env.filters['utc_datetime'] = self._utc_datetime_filter
        self.print_state(None)

    def print_state(self, db):
        force = True # Because otherwise 'summary_created' timestamp below is not updated
        if not db or self.generation != db.generation or force:
            self.start_page(self.list_fname)
            if not db or not db.pointer:
                self.pprint('Nothing here yet')
            else:
                template = self.env.get_template(self.template_name)
                self.generation = db.generation
                now = datetime.datetime.utcnow().replace(tzinfo=pytz.utc)
                dbptr = db.pointer
                data = {
                    'csets':             [],
                    'track_starttime':   dbptr['first_pointer']['timestamp'],
                    'track_endtime':     dbptr['timestamp'],
                    'tracked_hours':     (dbptr['timestamp']-dbptr['first_pointer']['timestamp']).total_seconds()/3600,
                    'summary_created':   now,
                    'pointer_timestamp': dbptr['timestamp'],
                    'first_seqno': dbptr['first_pointer']['seqno'],
                    'latest_seqno': dbptr['seqno']-1,
                    'generation': self.generation
                }
                cset_tracked_hours = 0
                #if state.area_chgsets:  # FIXME
                #    first_cset = state.area_chgsets[0]
                #    first_cset_ts = oc.Changeset.get_timestamp(state.area_chgsets_info[first_cset]['meta'])[1]
                #    cset_tracked_hours = (state.timestamp-first_cset_ts).total_seconds()/3600
                #    data['cset_first'] = first_cset_ts

                users = {}
                notes = 0
                csets_w_notes = 0
                csets_w_addr_changes = 0
                for c in db.chgsets_ready():
                    cid = c['cid']
                    meta = db.chgset_get_meta(cid)
                    info = db.chgset_get_info(cid)
                    user = meta['user']
                    users[user] = users.get(user,0) + 1
                    notecnt = int(meta['comments_count'])
                    if notecnt > 0:
                        notes += int(meta['comments_count'])
                        csets_w_notes += 1
                    if int(info['misc']['dk_address_node_changes'])>0:
                        csets_w_addr_changes += 1
                data['csets_with_notes'] = csets_w_notes
                data['csets_with_addr_changes'] = csets_w_addr_changes

                # Summarize edits and mileage - we don't do this incrementally
                # since csets can be split over multiple diffs
                edits = {'node':     {'create':0, 'modify':0, 'delete':0},
                         'way':      {'create':0, 'modify':0, 'delete':0},
                         'relation': {'create':0, 'modify':0, 'delete':0}}
                mileage = {}
                for c in db.chgsets_ready():
                    cid = c['cid']
                    info = db.chgset_get_info(cid)
                    data['csets'].append(c)
                    if 'truncated' in info['state']:
                        continue
                    summary = info['summary']
                    for action in ['create', 'modify', 'delete']:
                        if summary['_'+action] > 0:
                            for type in ['node', 'way', 'relation']:
                                edits[type][action] += summary[action][type]
                    self.merge_int_dict(mileage, info['mileage_m'])
                data['edits'] = edits
                data['users'] = users
                data['notes'] = notes
                logger.debug('Accumulated mileage: {}'.format(mileage))

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
                    data['mileage_meter'] = self._i2s(sum)
                    # Rounding means that if cset_tracked_hours=0, then we pretend the current
                    # metrics are for one hours
                    data['mileage_meter_per_hour'] = self._i2s(int(sum/max(1,cset_tracked_hours)))

                #if hasattr(state, 'pointer'):   # FIXME
                #    lag = now-state.pointer.timestamp()
                #    data['lag_seconds'] = int(lag.seconds)

                logger.debug('Data passed to template: {}'.format(data))
                self.pprint(template.render(data))
            self.end_page()
