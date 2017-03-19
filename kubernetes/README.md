# Deployment using Kubernetes

The 'all-in-one' container image
([michaelvl/osmtracker-all-in-one](https://hub.docker.com/r/michaelvl/osmtracker-all-in-one/))
is mainly intended as an easily approachable demonstrator.  For real production
deployments, the generic container image and the Kubernetes procedure described
below are recommended.

The Kubernetes deployment consists of the following resources

0. A MongoDB POD and a service definition for the database. All other PODs will use the database for persisting diff and changeset information.
0. A single stateless minutely diff tracker POD.
0. One or more stateless worker PODs for analyzing changesets.
0. One or more stateless frontend PODs which use a POD volume for sharing data between the osmtracker backend and the Nginx web server.

![Image](architecture.png?raw=true)

The three osmtracker container types all use the [michaelvl/osmtracker](https://hub.docker.com/r/michaelvl/osmtracker/) Docker image.

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
