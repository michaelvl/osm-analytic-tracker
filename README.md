## OpenStreetMap Analytic Difference Engine

OpenStreetMap Analytic Difference Engine is an analytic live (web) service for
OpenStreetMap (OSM) edits.  Edits are analysed and presented with a concise
summary.  The (text-based) summary is designed to provide a good insight into
what each changeset comtains (what was added, changed or deleted) and an
optional visual-diff provides insight into the geographical changes of each
changeset.

This live service is different from other OpenStreetMap live services in that it
focus on being analytic and less on being visual.

A running demo can be seen on http://osm.expandable.dk

The purpose of this tool is:

0. Prof-of-concept for an improved changeset-info service (improved compared to looking up changeset details on http://openstreetmap.org)
0. Provide insight into changes in your area of interest
0. Improve team spirit of a regional OSM team/task-force.
0. Quality ensurance through peer review
0. Learning by seeing how other make edits to your region of interest.

The service is available as a web-service and provide three different information elements:

0. An overall summary with a overview map containing bounding boxes of recent edits
0. A list of changesets with analytic details
0. A visual diff for the changes of each changeset

### Summary

The main page contain this overview in the top with OSM-user specific
colour-coded bounding boxes for each changeset and text-based summary for the
tracked time peried.

![Image](doc/summ2.png?raw=true)

### List of Changesets with changes

Green show added tags and how many additions the changeset contained.  Yellow show changed tags and red show deleted tags.

![Image](doc/csets.png?raw=true)

### Visual Diff

Geographical changes in the changeset, green are added objects, blue changed and red deleted. Each element can be clicked for more details.

![Image](doc/vdiff3.png?raw=true)
![Image](doc/vdiff.png?raw=true)

## How Does It Work?

TL;DR:

Run it using Docker:

```
docker run -p 8080:80 michaelvl/osmtracker
```

and point your browser to 127.0.0.1:8080

The manual approach:

0. Download a region polygon from e.g. http://download.geofabrik.de/
0. Change polygon filename in config.json to your chosen region
0. Run the main tracker as below
0. Inspect the files in the local html directory (can be customised also through the config.json file)
0. Optional - serve the html directory through a web-server.

```
tracker.py -lDEBUG
```

The tracker python script tracks OpenStreetMap minutely diffs and optionally
filters them through a bounding-box polygon (country-based polygons can be found
on http://download.geofabrik.de/).  Changesets found to be within the area of
interest are analysed further and a number of backends generate output.  The
HTML backends provide HTML data which can be served through a web-server.  The
client-side parts include a javascript-based poll feature that will update the
changeset list whenever it changes (special care has been taken to minimize
network load).

Do not track changes in a too large area or you might cause unreasonable load on
the OpenStreetMap API servers!  The definition of 'too-large' depends not on
geographical size, but the amount of changesets and the number of changes in
each changeset.  For each change (node, way, relation) in changesets within the
region, the old version is looked-up through the OSM API to figure out actual
differences, i.e. each change triggers an API lookup, and you basically want the
changeset analysis process to take less than a minute (because by default OSM
minutely diffs are tracked). The tracked supports multiple filter processes, but
using this will increase memory consumption. Experience has shown that a region
like Denmark is easily tracked using a low-end server.

Configuration is provided through the config.json file -- especially the paths
for the backends should be configured.

### Components

- tracker.py  The main script, tracks OpenStreetMap minutely diffs
- filter.py   Diff filter, filters a minutely diff through a region polygon and the analyse remaining changesets. Keeping this in a separate process improces control of memory consumption.
- OsmChangeset.py  The class, which contain the main analysis code.  Can be used from a command line through csetinfo.py

E.g. to view summary of a changeset (in json-format):

```
csetinfo.py -s -i <changeset-ID>
```

### Dependencies

- Python shapely and tilezone libraries:  python-shapepy python-tz
- Python OSM API: pip install osmapi
- Templates: pip install jinja2


### Links

* [Danish edits as seen through OSM Analytic Difference Engine](http://osm.expandable.dk)

* [Achavi diff viewer using overpass API](http://wiki.openstreetmap.org/wiki/Achavi)

* [Show Me The Way - a visual live service](http://osmlab.github.io/show-me-the-way/)

* [French OSM live service](http://live.openstreetmap.fr)
