#!/usr/bin/python

import sys, time
import argparse
import OsmDiff as osmdiff
import HumanTime
import logging, logging.config
import db as database
import config as configfile
import subprocess

logger = logging.getLogger('osmtracker')


def track_one(retries=3):
    args = ['./osmtracker.py', '-Odiff-fetch']
    attempts = 1
    while attempts<=retries:
        try:
            logger.debug("Calling '{}' - attempt {} of {}".format(args, attempts, retries))
            out = subprocess.check_output(args)
            logger.debug("Call returned: '{}'".format(args, out))
            return
        except subprocess.CalledProcessError as e:
            logger.warning('*** Subprocess error: {}'.format(e))
            time.sleep(60)
        attempts += 1
    logger.warn('Giving up processing diff seqno {}'.format(seqno))

def main(argv):
    logging.config.fileConfig('logging.conf')
    parser = argparse.ArgumentParser(description='OSM minutely diff tracker')
    parser.add_argument('-H', dest='history',
                        help='Define how much history to fetch')
    parser.add_argument('-w', dest='worker', default=False, action='store_true',
                        help='Become a worker processing changesets instead of a tracker')
    parser.add_argument('-l', dest='log_level', default='INFO',
                        choices=['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'],
                        help='Set the log level')

    args = parser.parse_args()
    logging.getLogger('').setLevel(getattr(logging, args.log_level))

    if args.worker:
        while True:
            cmd = ['./osmtracker.py', '-l', args.log_level, '-Ocset-check-bounds']
            out = subprocess.check_output(cmd)
            cmd = ['./osmtracker.py', '-l', args.log_level, '-Ocset-analyze']
            out = subprocess.check_output(cmd)
            cmd = ['./osmtracker.py', '-l', args.log_level, '-Orun-backends']
            out = subprocess.check_output(cmd)
            time.sleep(10)
    
    config = configfile.Config()
    config.load()

    db = database.DataBase()
    dapi = osmdiff.OsmDiffApi()

    head = dapi.get_state('minute')
    logger.debug('Head seqno is {}'.format(head.sequenceno))
    if args.history:
        history = HumanTime.human2date(args.history)
        pointer = dapi.get_seqno_le_timestamp('minute', history, head)
        db.pointer = seqno = pointer.sequenceno
    else:
        pointer = db.pointer
        if not pointer:
            logger.debug('No pointer defined - setting pointer to head {}'.format(head.sequenceno))
            db.pointer = seqno = head.sequenceno
        else:
            seqno = pointer['seqno']
    logger.debug('Tracking from seqno={}'.format(seqno))

    while True:
        head = dapi.get_state('minute')
        while head.sequenceno != db.pointer['seqno']:
            logger.debug('Head seqno {}, db.pointer seqno {}'.format(head.sequenceno, db.pointer['seqno']))
            track_one()
        time.sleep(60)

    
if __name__ == "__main__":
   sys.exit(main(sys.argv[1:]))
