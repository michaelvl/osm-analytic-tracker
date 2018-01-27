#!/usr/bin/env python

import os, sys, argparse
import logging, logging.config
import db as database
import time, datetime
import elasticsearch

logger = logging.getLogger(__name__)

def main():
    logging.config.fileConfig('logging.conf')
    parser = argparse.ArgumentParser(description='Elasticsearch gateway')
    parser.add_argument('-l', dest='log_level', default='INFO',
                        choices=['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'],
                        help='Set the log level')
    parser.add_argument('--db', dest='db_url', default='mongodb://localhost:27017/',
                        help='Set url for database')
    parser.add_argument('--amqp', dest='amqp_url', default='',
                        help='Set url for message bus')
    parser.add_argument('--configdir', dest='configdir', default='.',
                        help='Set path to config file')

    args = parser.parse_args()
    logging.getLogger('').setLevel(getattr(logging, args.log_level))

    db = database.DataBase(url=args.db_url)
    logger.debug('Connected to db: {}'.format(db))

    es_url = os.environ.get('ES_ENDPOINT')
    es = elasticsearch.Elasticsearch(hosts=es_url)

    es_index = os.environ.get('ES_OSMTRACKER_INDEX')

    last_update = None
    generation = None
    while True:
        logger.debug('Refreshing cset index')
        if generation != db.generation:
        #ts = datetime.datetime.now()
            for cset in db.chgsets_find(state=None, after=last_update, sort=False):
                del cset['_id']
                logging.info('Indexing cid {}'.format(cset['cid']))
                res = es.index(index=es_index, doc_type='cset', id=cset['cid'], body=cset)
                logging.info('Done: {}'.format(res))
            #last_update = ts
            generation = db.generation
        time.sleep(60)

if __name__ == "__main__":
   sys.exit(main())
