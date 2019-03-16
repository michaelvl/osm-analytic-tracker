FROM python:2-slim

# Debian/python base image
ENV DEBIAN_FRONTEND noninteractive
RUN apt-get -y update && apt-get install -y python-shapely wget && apt-get clean && rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*

RUN mkdir -p /osmtracker-test
WORKDIR /osmtracker-test

ADD requirements.txt .
ADD test-requirements.txt .
RUN pip install -r ./requirements.txt
RUN pip install -r ./test-requirements.txt

WORKDIR /osmtracker-test
ADD test ./test/
ADD osm/test ./osm/test/
ADD apiserver/test ./apiserver/test/

ADD osm/test/data/urls/planet.osm.org/replication/changesets/000/001/234.osm osm/test/data/urls/planet.osm.org/replication/changesets/000/001/234.osm
RUN gzip -c osm/test/data/urls/planet.osm.org/replication/changesets/000/001/234.osm > osm/test/data/urls/planet.osm.org/replication/changesets/000/001/234.osm.gz
