FROM python:2
#FROM debian:jessie
#FROM resin/rpi-raspbian

# Debian/python base image
ENV DEBIAN_FRONTEND noninteractive
RUN apt-get -y update && apt-get install -y python-shapely && apt-get clean && rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*

RUN mkdir -p /html-init/dynamic
COPY html/index.html html/addresses.html html/cset_notes.html html/diffmap.html html/styles.css html/att.png html/att_l.png html/csetopen.png html/csetopen_l.png html/dev_work.png html/err.png html/err_l.png html/favicon.png html/gear.png html/gear_l.png html/icon_bw.png html/josm-icon.png html/layers.png html/node.png html/note.png html/note_l.png html/osm-icon.png html/relation.png html/user.png html/user_l.png html/way.png html/leaflet-button.js html/timestamp.js /html-init/

RUN mkdir /html-init/jquery-2.1.3
ADD https://code.jquery.com/jquery-2.1.3.min.js /html-init/jquery-2.1.3/jquery.min.js

RUN mkdir -p /html-init/leaflet-0.7.7
ADD http://cdn.leafletjs.com/leaflet/v0.7.7/leaflet.css  /html-init/leaflet-0.7.7/leaflet.css
ADD http://cdn.leafletjs.com/leaflet/v0.7.7/leaflet.js /html-init/leaflet-0.7.7/leaflet.js

RUN chmod -R go+r /html-init/

RUN mkdir /osmtracker
ADD requirements.txt /osmtracker/
RUN pip install -r /osmtracker/requirements.txt

WORKDIR /osmtracker/osm-analytic-tracker
# Override requirements.txt for osmapi
RUN git clone https://github.com/MichaelVL/osmapi.git
ADD http://download.geofabrik.de/europe/denmark.poly region.poly

RUN mkdir /osmtracker-config
ADD config.json /osmtracker-config/
RUN sed -i 's/"path": "html"/"path": "\/html\/dynamic"/' /osmtracker-config/config.json

ADD *.py logging.conf ./
ADD osm ./osm
RUN mkdir /osmtracker/templates
ADD templates templates/

ENTRYPOINT ["python", "/osmtracker/osm-analytic-tracker/osmtracker.py", "--configdir", "/osmtracker-config"]
