FROM python:2-slim
#FROM resin/rpi-raspbian

# Debian/python base image
ENV DEBIAN_FRONTEND noninteractive
RUN apt-get -y update && apt-get install -y python-shapely wget && apt-get clean && rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*

RUN mkdir /osm-regions
WORKDIR /osm-regions
ADD docker/regions.txt .
RUN wget --no-verbose -i regions.txt

RUN mkdir -p /html-init/dynamic
COPY html/addresses.html html/cset_notes.html html/diffmap.html html/styles.css html/att.png html/att_l.png html/csetopen.png html/csetopen_l.png html/dev_work.png html/err.png html/err_l.png html/favicon.png html/gear.png html/gear_l.png html/icon_bw.png html/josm-icon.png html/layers.png html/node.png html/note.png html/note_l.png html/osm-icon.png html/relation.png html/user.png html/user_l.png html/bot_l.png html/way.png html/leaflet-button.js html/timestamp.js /html-init/

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

RUN mkdir /osmtracker-config
ADD config.json /osmtracker-config/
RUN sed -i 's/"path": "html"/"path": "\/html"/' /osmtracker-config/config.json

ADD *.py docker/logging.conf ./
ADD osm ./osm
ADD schemas ./schemas
ADD apiserver ./apiserver
RUN mkdir /osmtracker/templates
ADD templates templates/

# IDs>1000 since most Linux distros start allocating users from 1000
RUN groupadd -g 1042 osmtracker
RUN useradd -r -u 1042 -g osmtracker osmtracker
RUN chown -R osmtracker:osmtracker /osmtracker
# Numeric to allow for non-root test
USER 1042

ENTRYPOINT ["python", "/osmtracker/osm-analytic-tracker/osmtracker.py", "--configdir", "/osmtracker-config"]
