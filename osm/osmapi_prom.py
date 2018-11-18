# -*- coding: utf-8 -*-

"""
The OsmApi module is a wrapper for the OpenStreetMap API.

"""

import osmapi
import prometheus_client

# Node operations
m_events = prometheus_client.Counter('openstreetmap_api_events',
                                     'OpenStreetMap API requests',
                                     ['operation'])

m_bytes = prometheus_client.Counter('openstreetmap_api_bytes',
                                    'OpenStreetMap API bytes',
                                    ['operation', 'direction'])

class OsmApi(osmapi.OsmApi):

    #def __init__(self, *args, **kwargs):
    #    self.proxy = osmapi.OsmApi(*args, **kwargs)

    def _doop(self, op, *args, **kwargs):
        m_events.labels(op).inc()
        self.operation = op
        d = getattr(osmapi.OsmApi, op)(self, *args, **kwargs)
        self.operation = 'undef'
        return d
    
    ##################################################
    # Node                                           #
    ##################################################

    def NodeGet(self, *args, **kwargs):
        return self._doop('NodeGet', *args, **kwargs)

    def NodeHistory(self, *args, **kwargs):
        return self._doop('NodeHistory', *args, **kwargs)

    def NodeWays(self, *args, **kwargs):
        return self._doop('NodeWays', *args, **kwargs)

    def NodeRelations(self, *args, **kwargs):
        return self._doop('NodeRelations', *args, **kwargs)

    def NodesGet(self, *args, **kwargs):
        return self._doop('NodesGet', *args, **kwargs)

    # ##################################################
    # # Way                                            #
    # ##################################################

    def WayGet(self, *args, **kwargs):
        return self._doop('WayGet', *args, **kwargs)

    def WayHistory(self, *args, **kwargs):
        return self._doop('WayHistory', *args, **kwargs)

    def WayRelations(self, *args, **kwargs):
        return self._doop('WayRelations', *args, **kwargs)

    def WayFull(self, *args, **kwargs):
        return self._doop('WayFull', *args, **kwargs)

    def WaysGet(self, *args, **kwargs):
        return self._doop('WaysGet', *args, **kwargs)

    # ##################################################
    # # Relation                                       #
    # ##################################################

    def RelationGet(self, *args, **kwargs):
        return self._doop('RelationGet', *args, **kwargs)

    def RelationHistory(self, *args, **kwargs):
        return self._doop('RelationHistory', *args, **kwargs)

    def RelationRelations(self, *args, **kwargs):
        return self._doop('RelationRelations', *args, **kwargs)

    def RelationFullRecur(self, *args, **kwargs):
        return self._doop('RelationFullRecur', *args, **kwargs)

    def RelationFull(self, *args, **kwargs):
        return self._doop('RelationFull', *args, **kwargs)

    def RelationsGet(self, *args, **kwargs):
        return self._doop('RelationsGet', *args, **kwargs)

    # ##################################################
    # # Changeset                                      #
    # ##################################################

    def ChangesetGet(self, *args, **kwargs):
        return self._doop('ChangesetGet', *args, **kwargs)

    def ChangesetDownload(self, *args, **kwargs):
        return self._doop('ChangesetDownload', *args, **kwargs)

    def ChangesetsGet(self, *args, **kwargs):
        return self._doop('ChangesetsGet', *args, **kwargs)

    # ##################################################
    # # Notes                                          #
    # ##################################################

    def NotesGet(self, *args, **kwargs):
        return self._doop('NotesGet', *args, **kwargs)

    def NoteGet(self, *args, **kwargs):
        return self._doop('NoteGet', *args, **kwargs)

    ##################################################
    # Internal http function                         #
    ##################################################
    def _get(self, path):
        d = osmapi.OsmApi._get(self, path)
        m_bytes.labels(self.operation, 'rx').inc(len(d))
        return d
