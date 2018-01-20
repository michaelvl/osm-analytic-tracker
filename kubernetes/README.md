# Deployment using Kubernetes

The 'all-in-one' container image
([michaelvl/osmtracker-all-in-one](https://hub.docker.com/r/michaelvl/osmtracker-all-in-one/))
is mainly intended as an easily approachable demonstrator.  For real production
deployments, the generic container image and the Kubernetes procedure described
below are recommended.

The Kubernetes deployment consists of the following resources

1. A MongoDB deployment for the database. All other PODs will use the database for persisting diff and changeset information. This deployment is based on a MongoDB Helm subchart.
2. A RabbitMQ message queue deployment for communication between components. This deployment is based on a RabbitMQ Helm subchart.
3. A single stateless minutely diff tracker POD.
4. A changeset filtering deployment which performs initial filtering using labels and geometric rules.  Typically two pod are recommended for this deployment.
5. A changeset analyzer deployment which perform the full analysis of changesets which passes the defined filters.   Typically two pod are recommended for this deployment.
5. A frontend deployment which use a POD volume for sharing data between the osmtracker backend and the Nginx web server.
6. A supervisor service for monitoring state of worker PODs and for providing aggregated metrics for e.g. Prometheus.
7. An optional API server for add-on services - see the OpenAPI.Swagger [apispec.yaml](apiserver/apispec.yaml).
8. An optional Elasticsearch gateway, which pushes changeset information to Elasticsearch.

![Image](architecture.png?raw=true)

The three osmtracker container types all use the
[michaelvl/osmtracker](https://hub.docker.com/r/michaelvl/osmtracker/) Docker
image. Note that this image is using a non-root user with UID and GID of 1042
and the helm charts enforce a non-root user together with a read-only
filesystem.

An actual deployment can be created either using the Helm chart.  See the Helm
chart [README](helm/osm-analytic-tracker/README.md) for description of a
Helm-based deployment.

The default worker deployment use two filter and two analyzer instances,
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

The Helm-based deployment enable Prometheus-style metrics and a Grafana dashboard are available [here](osmtracker-grafana-dashboard.json?raw=true). The dashboard is shown below:

![Image](grafana-dashboard.png?raw=true)

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

## Kubernetes Network Policies

The Helm-based deployment supports deploying Kubernetes network policies to
allow for fine-grained control of network access between pods. You need a
Kubernetes network plugin that supports network policies for this to have any
effect.

If you are using a Kubernetes ingress/ingress-controller, you could refine the
osmtracker-frontend network policy selectors to match the labels of the
ingress. The same applies for the metrics network policy, which could be limited
to accept only connections from e.g. Prometheus.