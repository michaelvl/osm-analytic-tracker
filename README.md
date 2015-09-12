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

0. Download a region polygon from http://download.geofabrik.de/
0. Change polygon filename in config.json to your chosen region
0. Run the backend as below
0. Inspect the files in the local html directory (can be customised also through the config.json file)
0. Optional - serve the html directory through a web-server.

```
tracker.py -lDEBUG
```



The tracker python script tracks OpenStreetMap minutely diffs and optionally
filters them through a bounding-box polygon (country-based polygons can be found
on http://download.geofabrik.de/).  Changesets found to be within the area of
interest are anaylsed further and a number of backends generate output.  The
HTML backeds provide HTML data which can be served through a web-server.  The
client-side parts include a javascript-based poll feature that will update the
changeset list whenever it changes (special care has been taken to minimize
network load).

Do not track changes in a too large area or you might cause unreasonable load on
the OpenStreetMap API servers!

Configuration is provided through the config.json file -- especially the paths
for the backends should be configured.

### Links

* [Danish edits as seen through OSM Analytic Difference Engine] http://osm.expandable.dk

* [Show Me The Way](http://osmlab.github.io/show-me-the-way/) [source](https://github.com/osmlab/show-me-the-way)