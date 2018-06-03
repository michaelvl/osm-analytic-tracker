# -*- coding: utf-8 -*-

from __future__ import print_function
import BackendHtml
import datetime, pytz
import operator
import logging
import jinja2
import tempfilewriter
from os.path import join

logger = logging.getLogger(__name__)

class Backend(BackendHtml.Backend):

    def __init__(self, globalconfig, subcfg):
        super(Backend, self).__init__(globalconfig, subcfg)
        self.list_fname = self.build_filename(globalconfig, subcfg)
        self.template_name = subcfg['template']
        self.cfg = subcfg
        self.env = jinja2.Environment(loader=jinja2.FileSystemLoader(globalconfig.getpath('template_path', 'tracker')),
                                      trim_blocks=True, lstrip_blocks=True)
        self.env.filters['js_datetime'] = self._js_datetime_filter
        self.env.filters['utc_datetime'] = self._utc_datetime_filter
        self.horizon_hours = globalconfig.get('horizon_hours','tracker')

    def print_state(self, db, update_reason):
        force = True # Because otherwise 'summary_created' timestamp below is not updated
        if not db or self.generation != db.generation or force:
            if not db or not db.pointer:
                return
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
            cset_tracked_hours = (dbptr['timestamp']-dbptr['first_pointer']['timestamp']).total_seconds()/3600
            cset_tracked_hours = min(cset_tracked_hours, self.horizon_hours)
            users = {}
            notes = 0
            csets_w_notes = 0
            csets_w_addr_changes = 0
            for c in db.chgsets_find(state=[db.STATE_CLOSED, db.STATE_OPEN, db.STATE_ANALYSING2,
                                            db.STATE_REANALYSING, db.STATE_DONE], sort=False):
                data['csets'].append(c)
                cid = c['cid']
                meta = db.chgset_get_meta(cid)
                info = db.chgset_get_info(cid)
                user = meta['user']
                users[user] = users.get(user,0) + 1
                if meta['open'] or (info and 'truncated' in info['state']):
                    continue
                notecnt = int(meta['comments_count'])
                if notecnt > 0:
                    notes += int(meta['comments_count'])
                    csets_w_notes += 1
                if c['state'] != db.STATE_DONE:
                    continue
                if 'address-node-change' in c['labels']: #FIXME: does not belong here - this is configuration
                    csets_w_addr_changes += 1
            data['csets_with_notes'] = csets_w_notes
            data['csets_with_addr_changes'] = csets_w_addr_changes

            # Summarize edits and mileage - we don't do this incrementally
            # since csets can be split over multiple diffs
            edits = {'node':     {'create':0, 'modify':0, 'delete':0},
                     'way':      {'create':0, 'modify':0, 'delete':0},
                     'relation': {'create':0, 'modify':0, 'delete':0}}
            mileage = {}
            for c in db.chgsets_find(state=db.STATE_DONE, sort=False):
                cid = c['cid']
                info = db.chgset_get_info(cid)
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

            # Export info about analytics queue
            now = datetime.datetime.utcnow().replace(tzinfo=pytz.utc)
            oldest_ts = None
            processing_cnt = 0
            for c in db.chgsets_find(state=[db.STATE_NEW, db.STATE_BOUNDS_CHECK, db.STATE_BOUNDS_CHECKED,
                                            db.STATE_ANALYSING1, db.STATE_ANALYSING2], sort=False):
                age_s = (now-c['queued']).total_seconds()
                if oldest_ts is None or age_s > oldest:
                    oldest = age_s
                    oldest_cid = c['cid']
                    oldest_ts = c['queued']
                processing_cnt += 1
            data['processing_outstanding_cset_cnt'] = processing_cnt
            if oldest_ts:
                logging.info('Processing lag governed by cset {}, timestamp {}'.format(oldest_cid, oldest_ts))
                data['processing_oldest_outstanding_cset'] = oldest_ts

            #if hasattr(state, 'pointer'):   # FIXME
            #    lag = now-state.pointer.timestamp()
            #    data['lag_seconds'] = int(lag.seconds)

            logger.debug('Data passed to template: {}'.format(data))
            with tempfilewriter.TempFileWriter(self.list_fname) as f:
                f.write('<!-- Generated by OpenStreetMap Analytic Difference Engine -->')
                f.write(template.render(data))
