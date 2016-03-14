# -*- coding: utf-8 -*-

from __future__ import print_function
import Backend
import datetime, pytz
import HumanTime
import OsmDiff as osmdiff
import OsmChangeset as oc
import operator
import os
import logging
import jinja2

logger = logging.getLogger(__name__)

class Backend(Backend.Backend):

    def __init__(self, config, subcfg):
        super(Backend, self).__init__(config, subcfg)
        self.list_fname = config.getpath('path', 'BackendHtml')+subcfg['filename']
        #self.list_fname_old = config.getpath('path', 'BackendHtml')+config.get('filename_old', 'BackendHtml')
        self.js_timestamp_fmt = '%a, %d %b %Y %H:%M:%S %Z'
        self.template_name = subcfg['template']

        self.show_details = getattr(subcfg, 'show_details', True)
        self.show_comments = getattr(subcfg, 'show_comments', True)
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
            template = state.env.get_template(self.template_name)
            csets = state.area_chgsets
            ctx = { 'state': state}
            ctx['csets'] = csets[::-1]
            ctx['csets_err'] = state.err_chgsets
            ctx['csetinfo'] = state.area_chgsets_info
            ctx['show_details'] = self.show_details
            ctx['show_comments'] = self.show_comments
            logger.debug('Data passed to template: {}'.format(ctx))
            self.pprint(template.render(ctx))
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

    def no_items(self, state=None):
        if state:
            time = state.timestamp.strftime('%Y:%m:%d %H:%M:%S')
        else:
            time = datetime.datetime.utcnow().replace(tzinfo=pytz.utc)
            time = time.strftime('%Y:%m:%d %H:%M:%S')
        self.pprint('<p>No changesets at '+time+' (UTC)</p>')
