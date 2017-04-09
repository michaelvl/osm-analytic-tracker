FROM debian:jessie
#FROM resin/rpi-raspbian

ENV DEBIAN_FRONTEND noninteractive

RUN apt-get -y update && apt-get install -y supervisor git python python-pip python-shapely python-tz python-dev mongodb nginx wget

RUN mkdir /osm-regions
WORKDIR /osm-regions
ADD docker/regions.txt .
RUN wget --no-verbose -i regions.txt

RUN mkdir -p /data/db

RUN mkdir -p /html/dynamic
COPY html/addresses.html html/cset_notes.html html/diffmap.html html/styles.css html/att.png html/att_l.png html/csetopen.png html/csetopen_l.png html/dev_work.png html/err.png html/err_l.png html/favicon.png html/gear.png html/gear_l.png html/icon_bw.png html/josm-icon.png html/layers.png html/node.png html/note.png html/note_l.png html/osm-icon.png html/relation.png html/user.png html/user_l.png html/way.png html/leaflet-button.js html/timestamp.js /html/

RUN mkdir /html/jquery-2.1.3
ADD https://code.jquery.com/jquery-2.1.3.min.js /html/jquery-2.1.3/jquery.min.js

RUN mkdir -p /html/leaflet-0.7.7
ADD http://cdn.leafletjs.com/leaflet/v0.7.7/leaflet.css  /html/leaflet-0.7.7/leaflet.css
ADD http://cdn.leafletjs.com/leaflet/v0.7.7/leaflet.js /html/leaflet-0.7.7/leaflet.js

RUN chown -R www-data:www-data /html

COPY docker/config/nginx.conf /etc/nginx/nginx.conf
COPY docker/config/nginx-osmtracker.conf /etc/nginx/sites-enabled/default

RUN apt-get clean && rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*

RUN mkdir /osmtracker
ADD requirements.txt /osmtracker/
RUN pip install -r /osmtracker/requirements.txt

WORKDIR /osmtracker/osm-analytic-tracker

RUN mkdir /osmtracker-config
ADD config.json /osmtracker-config/
RUN sed -i 's/"path": "html"/"path": "\/html"/' /osmtracker-config/config.json

ADD *.py logging.conf ./
ADD osm ./osm
RUN mkdir /osmtracker/templates
ADD templates templates/

EXPOSE 80

ADD docker/supervisord.conf /osmtracker/
CMD ["/usr/bin/supervisord", "-c", "/osmtracker/supervisord.conf"]
