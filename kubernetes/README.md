# Deployment using Kubernetes

The 'all-in-one' container image
([michaelvl/osmtracker-all-in-one](https://hub.docker.com/r/michaelvl/osmtracker-all-in-one/))
is mainly intended as an easily approachable demonstrator.  For real production
deployments, the generic container image and the Kubernetes/Helm based procedure
described below are recommended.

The Kubernetes deployment consists of the following resources

1. A single stateless minutely diff tracker POD.
2. A changeset filtering deployment which performs initial filtering using labels and geometric rules.  Typically two pods are recommended for this deployment.
3. A changeset analyser deployment which perform the full analysis of changesets which passes the defined filters.   Typically two pods are recommended for this deployment.
4. A frontend deployment which use a POD volume for sharing data between the osmtracker backend and the Nginx web server.
5. A supervisor service for monitoring state of worker PODs and for providing aggregated metrics for e.g. Prometheus.
6. An optional API server for add-on services - see the OpenAPI.Swagger [apispec.yaml](apiserver/apispec.yaml).
7. An optional Elasticsearch gateway, which pushes changeset information to Elasticsearch.
8. A MongoDB deployment for the database in which replication state and individual changeset information is stored. All other PODs will use the database for persisting diff and changeset information. This deployment is based on a MongoDB Helm subchart.
9. A RabbitMQ message queue deployment for communication between components. This deployment is based on a RabbitMQ Helm subchart.

![Image](architecture.png?raw=true)

The osmtracker cocomponents all use the
[michaelvl/osmtracker](https://hub.docker.com/r/michaelvl/osmtracker/) Docker
image. Note that this image is using a non-root user with UID and GID of 1042
and the helm charts enforce a non-root user together with a read-only
filesystem.

See the Helm chart [README](helm/osm-analytic-tracker/README.md) for description
of the parameters available in the Helm chart.

The default worker deployment use two filter pods and two analyzer pods,
however, for larger regions it might ne necessary with more instance. To scale
the deployments do e.g.:

```
kubectl -n osmtracker scale deployment osmtracker-filter-deployment --replicas=3
```

For debugging you can run the osmtracker image interactively as follows:

```
kubectl run -it test --image michaelvl/osmtracker --command /bin/bash
```

## Metrics

The Helm-based deployment enable Prometheus-style metrics and a Grafana
dashboard are available [here](osmtracker-grafana-dashboard.json?raw=true). The
dashboard is shown below:

![Image](grafana-dashboard.png?raw=true)

The first row presents the general overview of the status of the tracker service
- the following rows contain information that is mostly useful for debugging
problems. The panels in the first row shows:

- Replication lag relative to OpenStreetMap. Since updates are published from
  OpenStreetMap every minute, the lag should generally be less than two minutes
  - worst case a little above two minutes.

- Replication sequence number rate. Since a new sequence number is used for each
  minutely diff from OpenStreetMap, this value should be approximately 1.

- The rate of changesets in the minutely diffs (i.e. changesets per
  minute). Generally this should be larger than zero (unless everyone stops
  editing OpenStreetMap data).

- The rate of changesets matching the filtering (hourly rate). Generally this
  should be larger than zero.

The metrics exported are:

- *osmtracker_changeset_cnt* - the number of changesets currently in the
   database. Labelled with changeset state. If changesets in e.g. state NEW or
   ANALYSING states it could mean the number of worker tasks cannot cope with
   the influx of new changesets.

- *osmtracker_minutely_diff_processing_time_seconds* - histogram with processing
   time for individual minutely diffs. Since the minutely diffs are parsed by a
   single entity this processing time should be less than one minute. Experience
   show this to be on the order of a few seconds on typical HW.

- *osmtracker_minutely_diff_timestamp* - currently observed timestamp from
   minutely diff. If this timestamp stops progressing it could mean a problem
   with OpenStreetMap replication, not the tracker service.

- *osmtracker_minutely_diff_processing_timestamp* - timestamp of latest minutely
   diff processing. This timestamp should typically be less than a minute plus a
   little allowance for processing the minutely diff, e.g. less than 70s.  If
   not, the tracker service might have an internal problem.

- *osmtracker_minutely_diff_head_seqno* - latest head sequence number observed from OpenStreetMap replication service.

- *osmtracker_minutely_diff_latest_seqno* - latest sequence number
   processed. Should be identical or very close to
   *osmtracker_minutely_diff_head_seqno*.

- *osmtracker_minutely_diff_csets_observed* - number of chagesets observed in
   the recent minutely diff. A very large influx of changesets might cause small
   increased delays in the tracker.

- *osmtracker_events* - changeset filter, analysis and changeset refresh events
   as indicated by 'event' label. Both generated and handled events are tracked
   as indicated by the 'action' label.

- *osmtracker_changeset_filter_processing_time_seconds* - histogram with
   processing time for filter events.

- *osmtracker_changeset_analysis_processing_time_seconds* - histogram with
   processing time for changeset analysis events.

- *osmtracker_changeset_refresh_processing_time_seconds* - histogram with
   processing time for changeset refresh events.

- *osmtracker_backend_processing_time_seconds* - histogram with processing time
   for backend refresh events.

## Kubernetes Network Policies

The Helm-based deployment supports deploying Kubernetes network policies to
allow for fine-grained control of network access between pods. You need a
Kubernetes network plugin that supports network policies for this to have any
effect.

If you are using a Kubernetes ingress/ingress-controller, you could refine the
osmtracker-frontend network policy selectors to match the labels of the
ingress. The same applies for the metrics network policy, which could be limited
to accept only connections from e.g. Prometheus.