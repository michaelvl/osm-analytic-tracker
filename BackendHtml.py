# -*- coding: utf-8 -*-

import os
import Backend
import datetime, pytz
import HumanTime
import osm.diff as osmdiff
import osm.changeset as oc
import osm.poly as poly
import operator
import logging
import jinja2
import tempfilewriter

logger = logging.getLogger(__name__)

class Backend(Backend.Backend):

    def __init__(self, globalconfig, subcfg):
        super(Backend, self).__init__(globalconfig, subcfg)
        self.list_fname = self.build_filename(globalconfig, subcfg)
        self.template_name = subcfg['template']
        self.cfg = subcfg
        # Interpret special keys
        if 'map_center' in self.cfg and type(self.cfg['map_center']) is dict:
            if self.cfg['map_center']['area_file_conversion_type'] == 'area_center':
                area = poly.Poly()
                if 'OSMTRACKER_REGION' in os.environ:
                    area_file = os.environ['OSMTRACKER_REGION']
                else:
                    area_file = self.cfg['map_center']['area_file']
                area.load(area_file)
                c = area.center()
                logger.debug("Loaded area polygon from '{}' with {} points, center {}".format(area_file, len(area), c))
                self.cfg['map_center'] = '{},{}'.format(c[1], c[0])
        if 'OSMTRACKER_MAP_SCALE' in os.environ:
            self.cfg['map_scale'] = os.environ['OSMTRACKER_MAP_SCALE']

        self.labels = subcfg.get('labels', None)

        self.show_details = subcfg.get('show_details', True)
        self.show_comments = subcfg.get('show_comments', True)
        self.last_chg_seen = None
        self.last_update = datetime.datetime.now()

        self.env = jinja2.Environment(loader=jinja2.FileSystemLoader(globalconfig.getpath('template_path', 'tracker')),
                                      trim_blocks=True, lstrip_blocks=True)
        self.env.filters['js_datetime'] = self._js_datetime_filter
        self.env.filters['utc_datetime'] = self._utc_datetime_filter

    def _js_datetime_filter(self, value):
        '''Jinja2 filter formatting timestamps in format understood by javascript'''
            # See javascript date/time format: http://tools.ietf.org/html/rfc2822#page-14
        JS_TIMESTAMP_FMT = '%a, %d %b %Y %H:%M:%S %z'
        return value.strftime(JS_TIMESTAMP_FMT)

    def _utc_datetime_filter(self, value):
        TIMESTAMP_FMT = '%Y:%m:%d %H:%M:%S'
        return value.strftime(TIMESTAMP_FMT)

    def print_state(self, db):
        now = datetime.datetime.now()
        #if now.day != self.last_update.day:
        #    print('Cycler - new day: {} {}'.format(now.day, self.last_update.day))
        #period = now-state.cset_start_time
        #if period.total_seconds() > self.config.get('horizon_hours', 'tracker')*3600:
        #    os.rename(self.list_fname, self.list_fname_old)
        #    print('Cycler')
        #    state.clear_csets()
        self.last_update = datetime.datetime.now()
        if self.generation != db.generation:
            self.generation = db.generation

            template = self.env.get_template(self.template_name)
            ctx = { 'csets': [],
                    'csets_err': [],
                    'csetmeta': {},
                    'csetinfo': {},
                    'show_details': self.show_details,
                    'show_comments': self.show_comments }
            # All Backend config with 'cfg_' prefix
            for k,v in self.cfg.iteritems():
                ctx['cfg_'+k] = v
            notes = 0
            csets_total = 0
            csets_w_notes = 0
            csets_w_addr_changes = 0
            for c in db.chgsets_find(state=[db.STATE_CLOSED, db.STATE_OPEN, db.STATE_ANALYSING2,
                                            db.STATE_REANALYSING, db.STATE_DONE]):
                logger.debug('Cset={}'.format(c))
                logger.debug('Backend labels {}, cset labels {}'.format(self.labels, c['labels']))
                csets_total += 1
                if self.labels and not set(c['labels']).intersection(self.labels):
                    continue
                cid = c['cid']
                ctx['csets'].append(c)
                info = db.chgset_get_info(cid)
                meta = db.chgset_get_meta(cid)
                ctx['csetmeta'][cid] = meta
                if info:
                    ctx['csetinfo'][cid] = info
                else:
                    logger.error('No info for cid {}: {}'.format(cid, c))
                    continue
                if meta['open'] or (info and 'truncated' in info['state']):
                    continue
                notecnt = int(meta['comments_count'])  # FIXME: This is duplicate w. BackendHtmlSummary.py
                if notecnt > 0:
                    notes += int(meta['comments_count'])
                    csets_w_notes += 1
                if c['state'] != db.STATE_DONE:
                    continue

                if 'address-node-change' in c['labels']: #FIXME: does not belong here - this is configuration
                    csets_w_addr_changes += 1
            ctx['csets_num_total'] = csets_total
            ctx['csets_with_notes'] = csets_w_notes
            ctx['csets_with_addr_changes'] = csets_w_addr_changes
            logger.debug('Data passed to template: {}'.format(ctx))
            with tempfilewriter.TempFileWriter(self.list_fname) as f:
                f.write('<!-- Generated by OpenStreetMap Analytic Difference Engine -->\n')
                f.write(template.render(ctx))

    def no_items(self, state=None):
        if state:
            time = state.timestamp.strftime('%Y:%m:%d %H:%M:%S')
        else:
            time = datetime.datetime.utcnow().replace(tzinfo=pytz.utc)
            time = time.strftime('%Y:%m:%d %H:%M:%S')
        return '<p>No changesets at '+time+' (UTC)</p>'
