## Deployment using Kubernetes

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

The three osmtracker container types all use the [michaelvl/osmtracker](https://hub.docker.com/r/michaelvl/osmtracker/) Docker image.

The Kubernetes deployment manifests can be found in the kubernetes folder.  Note
that the PODs are defined using ReplicationControllers and images are
un-versioned.  For newer Kubernetes versions you might want to use Deployments
or ScheduledJob Kubernetes objects.

![Image](architecture.png?raw=true)
