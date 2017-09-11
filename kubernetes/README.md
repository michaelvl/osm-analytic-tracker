# Deployment using Kubernetes

The 'all-in-one' container image
([michaelvl/osmtracker-all-in-one](https://hub.docker.com/r/michaelvl/osmtracker-all-in-one/))
is mainly intended as an easily approachable demonstrator.  For real production
deployments, the generic container image and the Kubernetes procedure described
below are recommended.

The Kubernetes deployment consists of the following resources

1. A MongoDB POD and a service definition for the database. All other PODs will use the database for persisting diff and changeset information.
2. A single stateless minutely diff tracker POD.
3. One or more stateless worker PODs for analyzing changesets.
4. One or more stateless frontend PODs which use a POD volume for sharing data between the osmtracker backend and the Nginx web server.
5. A supervisor service for monitoring state of worker PODs and for providing aggregated metrics for e.g. Prometheus.
6. An optional API server for add-on services - see the OpenAPI.Swagger [apispec.yaml](apiserver/apispec.yaml).
7. An optional Elasticsearch gateway, which pushes changeset information to Elasticsearch.

![Image](architecture.png?raw=true)

The three osmtracker container types all use the [michaelvl/osmtracker](https://hub.docker.com/r/michaelvl/osmtracker/) Docker image. Note that this image is using a non-root user with UID and GID of 945 and the helm charts enforce a non-root user together with a read-only filesystem.

An actual deployment can be created either using the Helm charts or stand-alone
yaml resource definitions.  See the Helm chart
[README](helm/osm-analytic-tracker/README.md) for description of a
Helm-based deployment.

## Deployment from resource manifests

The stand-alone Kubernetes deployment manifests can be found in the kubernetes
folder. Generally the Helm-based deployment is recommeded and the stand-alone
manifests will have fewer features.

The resources can be deployed as follows:

```
kubectl create -f osmtracker-namespace.yaml
kubectl create -f osmtracker-secrets.yaml
```

The secrets resource define database credentials - read-only for frontends and
read/write for other services. You might want to change the default credentials.

```
kubectl create -f osmtracker-database-service.yaml
kubectl create -f osmtracker-frontend-service.yaml
kubectl create -f osmtracker-database.yaml
kubectl create -f osmtracker-frontend.yaml
```

At this stage you can access the frontend service using a web-browser although
no changesets will be shown and the status on the right side will show a
'Loading...' message.

To begin tracking minutely diffs and analyze them, you need to deploy the
diff-tracker and worker pods as follows:

```
kubectl create -f osmtracker-difftracker.yaml
kubectl create -f osmtracker-worker.yaml
```

After a little while, the status panel should show tracker status and new
changesets should begin to appear.

The default worker deployment use a single worker instance, however, it is
recommended to use at least two, i.e. the deployment should be updated as
follows:

```
kubectl -n osmtracker scale deployment osmtracker-worker-deployment --replicas=2
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
   ANALYZING states it could mean the number of worker tasks cannot cope with
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
osmtracker-frontend network policy selectors to match the labels of the ingress.