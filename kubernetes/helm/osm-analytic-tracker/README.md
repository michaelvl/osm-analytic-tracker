# OpenStreetMap Analytic Tracker

This chart deploys [OpenStreetMap Analytic
Tracker](https://github.com/MichaelVL/osm-analytic-tracker), which is a tools
for continously analysing minutely diffs from OpenStreetMap, apply regional
filtering and display the changesets in a 'diff-style'.

## Deployment

```
git clone https://github.com/MichaelVL/osm-analytic-tracker.git
cd osm-analytic-tracker
helm install --name osmtracker --namespace osmtracker kubernetes/helm/osm-analytic-tracker
```

Note that you need to have helm initialized in your Kubernetes cluster before deploying.

## Configuration

The following table lists the configurable parameters of OpenStreetMap Analytic Tracker

| Parameter | Description | Default |
| --------- | ----------- | ------- |
| `difftracker.replicas` | Number of minutely diff trackers. Should generally not be changed! | 1 |
| `difftracker.resources.limits` | Service resource limits | `{cpu: 500m, memory: 1Gi}` |
| `difftracker.resources.requests` | Service resource requests | `{cpu: 100m,  memory: 512Mi}` |
| `difftracker.metrics.enabled` | Prometheus metrics support | True |
| `worker.replicas` | Number of agents analysing changesets. More than one is generally recommended. | 2 |
| `worker.resources.limits` | Worker resource limits | `{cpu: 500m, memory: 1Gi}` |
| `worker.resources.requests` | Worker resource requests | `{cpu: 50m, memory: 512Mi}` |
| `frontend.replicas` | Number of web frontends. Two recommended for HA during upgrade. | 2 |
| `frontend.service.name` | Name of frontend Kubernetes service | osmtracker-frontend |
| `frontend.service.type` | Frontend service type | NodePort |
| `frontend.service.externalPort` | If frontend service type is NodePort, this port is used | 30000 |
| `frontend.service.internalPort` | Internal port number. Points to internal web server | 80 |
| `osmtracker.image.image` | Image name for OpenStreetMap Analytic tracker services | michaelvl/osmtracker |
| `osmtracker.image.tag` | Image tag. See [here](https://hub.docker.com/r/michaelvl/osmtracker/tags/) | latest |
| `osmtracker.image.pullPolicy` | Image pull policy | IfNotPresent |
| `web.image.image` | Web server image | nginx |
| `web.image.tag` | Web server image tag | 1.11-alpine |
| `web.image.pullPolicy` | Web server image pull policy | IfNotPresent |
| `db.persistence.enabled` | Database persistence. Defaults to image ephemeral storage | false |
| `db.persistence.accessMode` | If storage enabled, this is the PVC access mode requested | ReadWriteOnce |
| `db.persistence.size` | If storage enabled, this is the PVC storage size requested| 8Gi |
| `db.users.admin` | Database admin user name | adm.user |
| `db.users.admin_pass` | Database admin password. It is highly recommended to change this from the default | adm.secret |
| `db.users.user_rw` | Database read-write user name. Used for worker access to database | rw.user |
| `db.users.user_rw_pass` | Database read-write user password. Used for worker access to database. It is highly recommended to change this from the default | rw.user.secret |
| `db.users.user_ro` | Database read-only user name. Used for web-frontend access to database | ro.user |
| `db.users.user_ro_pass` | Database read-only user password. Used for web-frontend access to database. It is highly recommended to change this from the default | ro.user.secret |
| `db.image.image` | Database image name | michaelvl/mongo |
| `db.image.tag` | Database image tag | 3.4.1-1 |
| `db.image.pullPolicy` | Database image pull policy | IfNotPresent |

Specify each parameter using the `--set key=value[,key=value]` argument to `helm
install`. For example,

```
helm install --name osmtracker --namespace osmtracker osm-analytic-tracker/kubernetes/helm/osm-analytic-tracker --set osmtracker.image.tag=66fc207
```
