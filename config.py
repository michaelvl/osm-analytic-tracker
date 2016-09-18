#!/usr/bin/env python

import json
import sys
import logging

logger = logging.getLogger(__name__)

class Config(object):
    def __init__(self):
        self.cfg = None

    def load(self, filename='config.json', path=''):
        with open(path+'/'+filename) as f:
            self.cfg = json.load(f)

    def get(self, what, who=None, default=None):
        '''Get config setting - first look in subconfig, if attribute is not there, look in global settings'''
        if who:
            subcfg = self.cfg.get(who, None)
            if subcfg:
                x = subcfg.get(what, None)
                if x:
                    return x
        c = self.cfg.get(what, None)
        logger.debug("get({}, {}) -> '{}'".format(what, who, c))
        if c:
            return c
        return default

    def getpath(self, what, who=None):
        '''Get path setting - concatinating global and sub configs'''
        #FIXME: Handle missing trailing '/' etc
        p1 = self.cfg.get(what, '')
        if who:
            subcfg = self.cfg.get(who, None)
            if subcfg:
                p2 = subcfg.get(what, '')
                c= p1+p2
                logger.debug("get({}, {}) -> '{}'".format(what, who, c))
                return c
        logger.debug("get({}, {}) -> '{}'".format(what, who, p1))
        return p1.rstrip('/')
