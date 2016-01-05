#!/usr/bin/python

import json
import sys
import logging

logger = logging.getLogger(__name__)

class Config(object):
    def __init__(self):
        self.cfg = None

    def load(self, filename):
        with open(filename) as f:
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
        return p1

if __name__=='__main__':
    c = Config()
    try:
        print "Test loading '{}'".format(sys.argv[1])
        c.load(sys.argv[1])
    except Exception as e:
        print 'Error parsing config file: {}'.format(e)
        sys.exit(-1)
    import pprint
    pprint.pprint(c.cfg)
    print 'get(path)={}'.format(c.get('path'))
    print 'getpath(path,BackendHtml)={}'.format(c.getpath('path', 'BackendHtml'))
    print 'get(filename,BackendHtml)={}'.format(c.get('filename', 'BackendHtml'))
    print 'get(filter,geosjondiff-filename)={}'.format(c.get('geosjondiff-filename', 'filter'))
    print 'get(filter, path+geojson-diff)={}'.format(c.get('path', 'tracker')+c.get('geojsondiff-filename', 'tracker'))
    print 'get(print_meta,BackendDetailed)={}'.format(c.get('print_meta','BackendDetailed'))
    
