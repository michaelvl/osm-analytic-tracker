#!/usr/bin/env python

import argparse
import os, io, sys
import kombu, kombu.mixins, kombu.pools
import json
import jsonschema
import avro.schema, avro.io
import base64
import logging

logger = logging.getLogger('messagebus')

class SchemaRegistry(object):
    def __init__(self):
        self.registry = {
        }
        self.path = 'schemas'

    def schema_get(self, schema, version=1):
        # FIXME store versions...
        if schema not in self.registry:
            self.registry[schema] = avro.schema.parse(open(os.path.join(self.path, schema, str(version))+'.avsc', "rb").read())
        return self.registry[schema]

ENVELOPE_SCHEMA = {
    'type': 'object',
    'properties': {
        'schema': {
            'type': 'string'
        },
        'version': {
            'type': 'integer',
            'minimum': 1
        },
        'message': {
            'type': 'string'
        }
    },
    'required': ['schema', 'version', 'message']
}

class Amqp(kombu.mixins.ConsumerProducerMixin):
    def __init__(self, url, exchange, exchange_type, declare_queues, handle_queues=None):
        logger.info('AMQP URL={}'.format(url))
        self.connection = kombu.Connection(url)
        self.exchange = kombu.Exchange(exchange, type=exchange_type)
        self.declare_queues = [kombu.Queue(name=n, exchange=self.exchange, routing_key=k) for n,k in declare_queues]
        if handle_queues:
            self.handle_queues = [kombu.Queue(name=n, exchange=self.exchange, routing_key=k) for n,k in handle_queues]
        logger.debug('Exchange {}, queues declared {}, handle queues {}'.format(exchange, declare_queues, handle_queues))
        self.schema_registry = SchemaRegistry()

    def __del__(self):
        logger.debug('AMQP cleanup...')

    def send(self, message, schema_name, schema_version, routing_key):
        schema = self.schema_registry.schema_get(schema_name, schema_version)
        writer = avro.io.DatumWriter(schema)
        bytes_writer = io.BytesIO()
        encoder = avro.io.BinaryEncoder(bytes_writer)
        writer.write(message, encoder)
        raw_bytes = bytes_writer.getvalue()
        msg = {
            'schema': schema_name,
            'version': schema_version,
            'message': base64.b64encode(raw_bytes)#json.dumps(message)
        }
        self.producer.publish(msg, exchange=self.exchange,
                              declare = self.declare_queues,
                              routing_key=routing_key, retry=True)

    def get_consumers(self, Consumer, channel):
        logger.debug('Consumer queues: {}'.format(self.handle_queues))
        return [Consumer(
            queues = self.handle_queues,
            on_message = self.message_cb,
            accept = {'application/json'},
            prefetch_count = 1,
        )]

    def message_cb(self, message):
        msg = message.payload
        jsonschema.validate(msg, ENVELOPE_SCHEMA)
        schema = self.schema_registry.schema_get(msg['schema'], msg['version'])

        bytes_reader = io.BytesIO(base64.b64decode(msg['message']))
        decoder = avro.io.BinaryDecoder(bytes_reader)
        reader = avro.io.DatumReader(schema)
        msg = reader.read(decoder)
        
        self.on_message(msg, message)

    def on_message(self, payload, message):
        message.ack()


class TestAmqp(Amqp):
    def on_message(self, payload, message):
        print payload
        message.ack()

def test_recv(args):
    logging.debug('Entering test_recv(), key={}'.format(args.key))
    amqp = TestAmqp(args.url, args.exchange, [(args.queue, args.key)])
    amqp.run()


if __name__ == '__main__':

    parser = argparse.ArgumentParser(description='AMQP Test')
    parser.add_argument('-l', dest='log_level', default='INFO',
                        choices=['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'],
                        help='Set the log level')
    #parser.add_argument('--url', default='amqp://guest:guest@localhost:5672')
    parser.add_argument('--url', default='amqp://osmtracker-amqp')
    parser.add_argument('--exchange', default='osmtracker')
    subparsers = parser.add_subparsers()

    parser_recv = subparsers.add_parser('recv')
    parser_recv.set_defaults(func=test_recv)
    parser_recv.add_argument('--key', default='new_cset.osmtracker')
    parser_recv.add_argument('--queue', default=None)

    args = parser.parse_args()
    logging.getLogger('').setLevel(getattr(logging, args.log_level))

    sys.exit(args.func(args))
