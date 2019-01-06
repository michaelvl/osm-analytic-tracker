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

The typical customization is to specify a different region than denmark and
possibly also a different initial zoom value for the overview map. This can be
done by passing alternative values to helm:

```
helm install --name osmtracker --namespace osmtracker kubernetes/helm/osm-analytic-tracker --set osmtracker.region=/osm-regions/sweden.poly,osmtracker.map_scale=4
```

Note that you need to have helm initialized in your Kubernetes cluster before deploying.

## Configuration

The following table lists the configurable parameters of OpenStreetMap Analytic Tracker

| Parameter | Description | Default |
| --------- | ----------- | ------- |
| `osmtracker.image.region` | Area to use for filtering changesets | /osm-regions/denmark.poly |
| `osmtracker.image.map_scale` | Initial zoom for overview map | 6 |
| `osmtracker.image.image` | Image name for OpenStreetMap Analytic tracker services | michaelvl/osmtracker |
| `osmtracker.image.tag` | Image tag. See [here](https://hub.docker.com/r/michaelvl/osmtracker/tags/) | latest |
| `osmtracker.image.pullPolicy` | Image pull policy | IfNotPresent |
| `osmtracker.networkpolicy.enabled` | Selects deployment of Kubernetes network policies | true |
| `osmtracker.dashboardConfigMap.enabled` | Selects deployment ConfigMap with Grafana dashboard | false |
| `osmtracker.metrics.enabled` | Prometheus metrics support | True |
| `difftracker.replicas` | Number of minutely diff trackers. Should generally not be changed! | 1 |
| `difftracker.resources.limits` | Service resource limits | `{cpu: 250m, memory: 1Gi}` |
| `difftracker.resources.requests` | Service resource requests | `{cpu: 50m,  memory: 512Mi}` |
| `filter.replicas` | Filter task of agents analysing changesets. More than one is generally recommended. | 2 |
| `filter.resources.limits` | Filter task resource limits | `{cpu: 250m, memory: 1Gi}` |
| `filter.resources.requests` | Filter task resource requests | `{cpu: 50m, memory: 512Mi}` |
| `analyser.replicas` | Analyser task of agents analysing changesets. More than one is generally recommended. | 2 |
| `analyser.resources.limits` | Analyser task resource limits | `{cpu: 250m, memory: 1Gi}` |
| `analyser.resources.requests` | Analyser task resource requests | `{cpu: 50m, memory: 512Mi}` |
| `frontend.replicas` | Number of web frontends. Two recommended for HA during upgrade. | 1 |
| `frontend.service.name` | Name of frontend Kubernetes service | osmtracker-frontend |
| `frontend.service.type` | Frontend service type | NodePort |
| `frontend.service.externalPort` | If frontend service type is NodePort, this port is used | 30000 |
| `frontend.service.internalPort` | Internal port number. Points to internal web server | 80 |
| `frontend.dev_notes` | Notes to display for e.g. development versions | '' |
| `apiserver.enabled` | API server enable. | false |
| `apiserver.replicas` | Number of API server instances. Two recommended for HA during upgrade. | 1 |
| `apiserver.service.name` | Name of API server Kubernetes service | osmtracker-apiserver |
| `apiserver.service.type` | API server service type | NodePort |
| `apiserver.service.externalPort` | If API server service type is NodePort, this port is used | 30001 |
| `web.image.image` | Web server image | nginx |
| `web.image.tag` | Web server image tag | 1.11-alpine |
| `web.image.pullPolicy` | Web server image pull policy | IfNotPresent |
| `db.persistence.enabled` | Database persistence. Defaults to image ephemeral storage | false |
| `db.persistence.volume.storageClass` | PVC storage class | null |
| `db.persistence.volume.accessMode` | PVC access mode | ReadWriteOnce |
| `db.persistence.volume.size` | PVC storage size request| 8Gi |
| `db.users.admin` | Database admin user name | adm.user |
| `db.users.admin_pass` | Database admin password. It is highly recommended to change this from the default | adm.secret |
| `db.users.user_rw` | Database read-write user name. Used for worker access to database | rw.user |
| `db.users.user_rw_pass` | Database read-write user password. Used for worker access to database. It is highly recommended to change this from the default | rw.user.secret |
| `db.users.user_ro` | Database read-only user name. Used for web-frontend access to database | ro.user |
| `db.users.user_ro_pass` | Database read-only user password. Used for web-frontend and API server access to database. It is highly recommended to change this from the default | ro.user.secret |
| `db.image.image` | Database image name | michaelvl/mongo |
| `db.image.tag` | Database image tag | 3.4.1-1 |
| `db.image.pullPolicy` | Database image pull policy | IfNotPresent |
| `elasticsearch_gw.enabled` | Elasticsearch gateway enable | false |
| `elasticsearch_gw.elasticsearch_url` | URL for Elasticssearch service | 'http://elastic:changeme@osmtracker-elasticsearch:9200' |
| `elasticsearch_gw.elasticsearch_index` | Elasticsearch index to use for pushing changeset info | 'osmtracker' |
| `elasticsearch_gw.resources.limits` | Elasticsearch gateway resource limits | { cpu: 500m, memory: 1Gi } |
| `elasticsearch_gw.resources.requests` | Elasticsearch gateway resource requests | { cpu: 50m, memory: 512Mi } |
| `openstreetmap.externalApiService.enabled` | Enable service for external OSM API | true |
| `openstreetmap.externalApiService.name` | Name of service referencing external OSM API | 'openstreetmap-api' |
| `openstreetmap.externalApiService.url` | URL for external OSM API | 'https://api.openstreetmap.org' | 

Specify each parameter using the `--set key=value[,key=value]` argument to `helm
install`. For example,

```
helm install --name osmtracker --namespace osmtracker osm-analytic-tracker/kubernetes/helm/osm-analytic-tracker --set osmtracker.image.tag=git-393a0cf,osmtracker.region=/osm-regions/denmark.poly
```

For the most recent images, see [here](https://hub.docker.com/r/michaelvl/osmtracker/tags/)
