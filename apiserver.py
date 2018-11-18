#!/usr/bin/env python

import os
import argparse
import datetime, pytz
import connexion
import logging, logging.config
import apiserver.api as api
import db as database

logger = logging.getLogger('osmtracker-api')

app = connexion.App(__name__)
app.add_api('apiserver/apispec.yaml')

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='OSM Analytic Tracker API Server')
    parser.add_argument('-l', dest='log_level', default='INFO',
                        choices=['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'],
                        help='Set the log level')
    parser.add_argument('--db', dest='db_url', default='mongodb://localhost:27017/',
                        help='Set url for database')
    parser.add_argument('--amqp', dest='amqp_url', default='',
                        help='Set url for message bus')
    parser.add_argument('--metrics', dest='metrics', action='store_true', default=False,
                        help='Enable metrics through Prometheus client API')
    parser.add_argument('--metricsport', dest='metricsport', type=int, default=8000,
                        help='Port through which to serve metrics')
    parser.add_argument('--configfile', dest='configfile', default='./config.json',
                        help='Set config file')

    args = parser.parse_args()
    logging.getLogger('').setLevel(getattr(logging, args.log_level))

    api.app = app
    app.db = database.DataBase(url=args.db_url, admin=False)
    logger.debug('Connected to db: {}'.format(app.db))

    port = int(os.environ.get('PORT', 5000))
    app.run(#server='tornado',
        #server='gevent',
        host='0.0.0.0', port=port)
