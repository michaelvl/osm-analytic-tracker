FROM debian:jessie

RUN apt-get -y update && apt-get install -y supervisor git python python-pip python-shapely python-tz
RUN apt-get install -y nginx
RUN apt-get clean && rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*

RUN mkdir -p /html/dynamic

RUN mkdir /html/jquery-2.1.3
ADD https://code.jquery.com/jquery-2.1.3.min.js /html/jquery-2.1.3/jquery.min.js

RUN mkdir -p /html/leaflet-0.7.7
ADD http://cdn.leafletjs.com/leaflet/v0.7.7/leaflet.css  /html/leaflet-0.7.7/leaflet.css
ADD http://cdn.leafletjs.com/leaflet/v0.7.7/leaflet.js /html/leaflet-0.7.7/leaflet.js

RUN chown -R www-data:www-data /html

COPY config/nginx.conf /etc/nginx/nginx.conf
COPY config/nginx-osmtracker.conf /etc/nginx/sites-enabled/default

RUN mkdir /osmtracker

WORKDIR /osmtracker/
RUN git clone https://github.com/MichaelVL/osm-analytic-tracker.git

WORKDIR /osmtracker/osm-analytic-tracker
COPY config/osmtracker.json config.json
RUN pip install -r /osmtracker/osm-analytic-tracker/requirements.txt
RUN git clone https://github.com/MichaelVL/osmapi.git
ADD http://download.geofabrik.de/europe/denmark.poly region.poly

RUN cp -r html/* /html/
RUN sed -i 's/"path": "html"/"path": "\/html\/dynamic"/' ./config.json

EXPOSE 80

ADD config/supervisord.conf /
CMD ["/usr/bin/supervisord", "-c", "/supervisord.conf"]
