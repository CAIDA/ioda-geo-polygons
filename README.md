# CAIDA IODA Polygons

Geographical polygons datasets and associated scripts created as part of CAIDA's
[Internet Outages Detection and Analysis (IODA) project](https://ioda.caida.org).

In addition to continent-, country-, and region-level polygons, the
[scripts/](scripts/) directory contains scripts that can be used (after
customization) to join the polygon datasets with an IP-geolocation dataset.

## Polygons

We provide both [geojson](geojson/) and [topojson](topojson/) formatted polygon
files to simplify use in Web applications. Currently we make available polygons
at three levels: continent, country, and region. All these datasets are based on
data from the Natural Earth project. The "region" dataset is based on a
semi-manual selection and stitching together of sub-national polygons (e.g., US
states) from the Natural Earth dataset.

Each polygon in the datasets has (at least) `id`, `fqid`, `name`, and `usercode`
fields. (See [scripts/gen-polygon-table.py](scripts/gen-polygon-table.py) for a
script to extract these fields as a CSV.)

## Scripts

### gen-polygon-table.py

This is a simple script to extract `id`, `fqid`, `name`, and `usercode` fields
from a polygons file in CSV format. This can then be used as a "join" table in
conjunction with the output from the "gen-loc-polygon-join-table.py" script.

See [polygons/](polygons/) for sample output from this script.

### gen-loc-polygon-join-table.py

This script takes as input the "locations" table from an IP geolocation database
and a geojson polygons file, and attempts to map each location to the best
polygon. The current implementation is designed specifically for a "locations"
table from the Net Acuity IP geolocation database, so will need to be adapted
for use with other databases.

## Acknowledgments

Datasets in this project have been made from data from the
[Natural Earth](http://www.naturalearthdata.com/) project.
