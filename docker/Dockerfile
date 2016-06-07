FROM phusion/baseimage

RUN mkdir /osmtracker
WORKDIR /osmtracker
RUN apt-get -y update && apt-get install -y git python python-pip python-shapely python-tz
RUN apt-get install -y nginx
RUN pip install osmapi tzlocal jinja2
RUN git clone https://github.com/MichaelVL/osmapi.git
RUN git clone https://github.com/MichaelVL/osm-analytic-tracker.git
WORKDIR /osmtracker/osm-analytic-tracker
COPY config/osmtracker.json config.json
ADD http://download.geofabrik.de/europe/denmark.poly region.poly

RUN mkdir /etc/service/osmtracker
COPY runit/osmtracker /etc/service/osmtracker/run

RUN cp -r html /
RUN mkdir /html/dynamic

RUN mkdir /html/jquery-2.1.3
ADD https://code.jquery.com/jquery-2.1.3.min.js /html/jquery-2.1.3/jquery.min.js

RUN mkdir /html/leaflet-0.7.7
ADD http://cdn.leafletjs.com/leaflet/v0.7.7/leaflet.css  /html/leaflet-0.7.7/leaflet.css
ADD http://cdn.leafletjs.com/leaflet/v0.7.7/leaflet.js /html/leaflet-0.7.7/leaflet.js

RUN chown -R www-data:www-data /html

COPY config/nginx.conf /etc/nginx/nginx.conf
COPY config/nginx-osmtracker.conf /etc/nginx/sites-enabled/default

RUN mkdir /etc/service/nginx
COPY runit/nginx /etc/service/nginx/run

RUN apt-get clean && rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*

EXPOSE 80

CMD ["/sbin/my_init"]
