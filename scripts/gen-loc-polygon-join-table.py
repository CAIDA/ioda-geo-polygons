#!/usr/bin/env python
#
# This software is Copyright © 2014 The Regents of the University of
# California. All Rights Reserved. Permission to copy, modify, and distribute
# this software and its documentation for educational, research and non-profit
# purposes, without fee, and without a written agreement is hereby granted,
# provided that the above copyright notice, this paragraph and the following
# three paragraphs appear in all copies. Permission to make commercial use of
# this software may be obtained by contacting:
#
# Office of Innovation and Commercialization
# 9500 Gilman Drive, Mail Code 0910
# University of California
# La Jolla, CA 92093-0910
# (858) 534-5815
# invent@ucsd.edu
#
# This software program and documentation are copyrighted by The Regents of the
# University of California. The software program and documentation are supplied
# "as is", without any accompanying services from The Regents. The Regents does
# not warrant that the operation of the program will be uninterrupted or
# error-free. The end-user understands that the program was developed for
# research purposes and is advised not to rely exclusively on the program for
# any reason.
#
# IN NO EVENT SHALL THE UNIVERSITY OF CALIFORNIA BE LIABLE TO ANY PARTY FOR
# DIRECT, INDIRECT, SPECIAL, INCIDENTAL, OR CONSEQUENTIAL DAMAGES, INCLUDING
# LOST PROFITS, ARISING OUT OF THE USE OF THIS SOFTWARE AND ITS DOCUMENTATION,
# EVEN IF THE UNIVERSITY OF CALIFORNIA HAS BEEN ADVISED OF THE POSSIBILITY OF
# SUCH DAMAGE. THE UNIVERSITY OF CALIFORNIA SPECIFICALLY DISCLAIMS ANY
# WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED WARRANTIES OF
# MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE. THE SOFTWARE PROVIDED
# HEREUNDER IS ON AN "AS IS" BASIS, AND THE UNIVERSITY OF CALIFORNIA HAS NO
# OBLIGATIONS TO PROVIDE MAINTENANCE, SUPPORT, UPDATES, ENHANCEMENTS, OR
# MODIFICATIONS.
#
__author__	= "Vasco Asturiano"
__email__	= "vasco@caida.org"
__version	= "1.0.0"

import csv
import json
import argparse
import sys
import gzip

from shapely.geometry import shape, Point

#######

#### Dataset join params

NETACQ_CC_PROPERTY = 'edge-two-letter-country'
GEOJSON_CC_PROPERTY = 'iso2cc'  # Which property to use for CC to join with netacuity
GEOJSON_POLYGON_ID = ['id']     # Which combined properties to use for logging polygon ID

CC_MAPPING = {   # Artificial CC mapping for countries which use different CCs in Netacuity and the GeoJSON
    'uk': 'gb',  # Conversion to ISO 3166-1
    're': 'fr',  # French overseas territories
    'gp': 'fr',
    'gf': 'fr',
    'yt': 'fr',
    'bq': 'fr',
    'bv': 'fr',
    'tk': 'nz', # Tokelau > New Zealand
    'sj': 'no', # Svalbard > Norway
    'cx': 'cx', # Indian Ocean Territories
    'cc': 'cc'
}

####

PROXIMITY_THRESHOLD = 20 # km. For validating border points that are located 'slightly' out of their
                         # correct region polygon due to geometrical resolution aliasing issues

DEGREE2KM = 111         # How many (avg) kms in a lat/long degree (doesn't account for polar flattening, but it'll do)

####

# In ascending resolution order. Val field,Confidence level field,Output name
levelsHierarchy = [
    ('edge-continent-code', None, 'continent'),
    (NETACQ_CC_PROPERTY,'edge-country-conf','country'),
    ('edge-region','edge-region-conf','region'),
    ('edge-city','edge-city-conf','city'),
    ('edge-postal-code','edge-postal-conf','postal-code')
]

def getHierarchyLevel(levelName):
    return reduce(lambda prev,(i,l): i if l[2]==levelName else prev,enumerate(levelsHierarchy),0)

####

env = {}

#######

# CLI syntax

cliParser = argparse.ArgumentParser(description="""
    For each unique location in a Net Acuity locations file, figures out the
    matching id of the polygon in a regions GeoJSON file using a brute-force approach.
    If no acceptable match can be found, the field is empty.
    Some countries can't be trusted for mapping Net Acuity regional level centroids
    to regions in a GeoJSON file, because of total different fragmentation methods
    used (example: districts vs provinces). This is mostly problematic when there are more
    regions in the GeoJSON than in Net Acuity for a given country, because the centroid
    of the Net Acuity region will give biased weight to a smaller region in the GeoJSON.
    The list of 'untrusted' countries can be inputted using the blacklist input csv file.
	""")

cliParser.add_argument('-l',  '--netacuity_locations_csv_file',
					nargs='?', required=True,
                    help='The path to the Netacuity locations file (csv format).'
)
cliParser.add_argument('-g',  '--regions_geojson_files',
					nargs='?', required=True,
                   	help='The path to the regions GeoJSON file(s) (multiple geoJson can be added comma separated, '
                         'which will cause multiple polygon columns to be present in the output table).'
)
cliParser.add_argument('-c',  '--min_conf_levels',
					nargs='?', required=True,
                   	help='Possible values: ' + ', '.join([level[2] for level in levelsHierarchy]) + '. The '
                         'minimum confidence level of a Net Acuity location required for running the matching with each '
                         'of the GeoJson files. There must be explicitly one confidence level set per GeoJson file '
                         '(comma separated), and in the same order.'
)
cliParser.add_argument('-t',  '--conf_threshold',
					nargs='?', required=False, default=51,
                    help='Default: 51. Percentage threshold (0-100) for validating the confidence levels. Values above this '
                         'threshold will determine that the location point has geoloc confidence at that level (country, region, etc).'
)
cliParser.add_argument('-b',  '--blacklist_ccs_csv_file',
					nargs='?', default=None, required=False,
                   	help='Optional. The path to the file with list of untrusted countries regarding Net Acuity<GeoJSON region '
                         'matching file (csv format)'
)

env.update(vars(cliParser.parse_args()))

# Split GeoJson filepath names
env["regions_geojson_files"] = [fp.strip() for fp in env["regions_geojson_files"].split(',')]

# Parse confidence levels
env["min_conf_levels"] = [cl.strip().lower() for cl in env["min_conf_levels"].split(',')]
if len(env["regions_geojson_files"]) != len(env["min_conf_levels"]):
    sys.exit('There must be the same number of Geojson files (' + str(len(env["regions_geojson_files"])) + ') '
             'and min confidence levels (' +  str(len(env["min_conf_levels"])) +').')

for cl in env["min_conf_levels"]:
    if not cl in [level[2] for level in levelsHierarchy]:
        sys.exit('Unrecognised confidence level: ' + cl +'. Allowed values: ' + ','.join([level[2] for level in levelsHierarchy]))
env["min_conf_levels"] = map(getHierarchyLevel, env["min_conf_levels"])

try:
    env['conf_threshold'] = float(env['conf_threshold'])
    if env['conf_threshold']<0 or env['conf_threshold']>100:
        sys.exit('Confidence threshold represents a percentage and must be between 0 and 100.')
except:
    sys.exit('Unable to parse confidence threshold ' + env['conf_threshold'] + ' to number.')

#######

def getGeoJsonData():
    return map(loadGeoJsonFile, env["regions_geojson_files"])

def loadGeoJsonFile(filePath):
    sys.stderr.write("loading " + filePath + "\n")

    regions = {}

    with open(filePath) as geoJsonFile:
        geoJsonReader = json.load(geoJsonFile)

        for region in geoJsonReader["features"]:
            cc = region["properties"][GEOJSON_CC_PROPERTY].lower()
            region["properties"][GEOJSON_CC_PROPERTY] = cc

            if cc == '-1':  # Region not bound to a country
                continue

            regions.setdefault(cc, [])
            regions[cc].append(region)

            # Create shape object only once for algorithmic efficiency
            region["shape"] = shape(region["geometry"]) if region["geometry"] else None # Some are dummy geometries (unknown regions)

        tableName = geoJsonReader['table-name'] if 'table-name' in geoJsonReader else None


    sys.stderr.write("done loading " + filePath + "\n")
    return (tableName,regions)

def getBlacklistCountries():
    filePath = env["blacklist_ccs_csv_file"]

    if not filePath: # No blacklisted countries
        return []

    sys.stderr.write("loading " + filePath + "\n")

    ccs = reduce(lambda prev, cur: prev+cur, csv.reader(open(filePath, 'r')), [])

    sys.stderr.write("done loading " + filePath + "\n")
    return ccs

######

def getPolygon(polygons, lat, long, cc, prevMatch):

    point = Point(long, lat)

     # chances are the region for this point is the same as the
     # last one, so check that before we search all
    if prevMatch and cc == prevMatch['properties'][GEOJSON_CC_PROPERTY] \
            and prevMatch["shape"].contains(point):
        return prevMatch

    # test this location's coordinates against every polygon in the country
    for r in polygons[cc]:
        if r["shape"].contains(point):
            return r

    # Check closest region
    closeRegions = filter(
        lambda r: r[1]<PROXIMITY_THRESHOLD,
        map(lambda r: (r, point.distance(r['shape'])*DEGREE2KM), polygons[cc])
    )

    if len(closeRegions):
        closestRegion = min(closeRegions, key = lambda r: r[1])
        #print "Found closest region, at distance: " + str(closestRegion[1]) + "km"
        return closestRegion[0]

    #sys.stderr.write("Closest region outside distance threshold: "
    #    + str(min(map(lambda r: point.distance(r['shape']), polygons[cc]))*DEGREE2KM)
    #    + "km\n")

    return None


def processLocation(loc, polygonSets, unknownPolygonSets, blackListCountries):

    def writeRow(location, matchingPolygons):
        def getPolygonId(polygon):
            return '.'.join(
                [str(polygon['properties'][propId] if propId in polygon['properties'] else '')
                    for propId in GEOJSON_POLYGON_ID
                ]
            )

        sys.stdout.write(','.join(
            [location['locid']] + map(getPolygonId, matchingPolygons)
        ) + "\n")

    bestLevel = len(levelsHierarchy)
    for level in reversed(levelsHierarchy):
        bestLevel-=1
        val = loc[level[0]]
        conf = int(loc[level[1]]) if (level[1] and level[1] in loc) else 100
        if val and not val in ('?','0','-1','no region') and conf >= env['conf_threshold']:    # Level match
            break

    cc = loc[NETACQ_CC_PROPERTY].lower()

    if cc=='**':   # Dummy location point for private/reserved space. Can't geolocate.
        for idx,unknownPolygons in enumerate(unknownPolygonSets):
            if not '??' in unknownPolygons or not len(unknownPolygons['??']):
                sys.exit('Unable to find unknown country polygon ("??" expected) in GeoJson file at position ' + str(idx+1))

        writeRow(loc, [unknownPolygons['??'][0] for unknownPolygons in unknownPolygonSets])
        return

    if cc in CC_MAPPING:
        cc = CC_MAPPING[cc]

    lat = float(loc['edge-latitude'])
    long = float(loc['edge-longitude'])

    # Keep track of previous matches for algorithmic efficiency
    if not processLocation.prevMatches:
        processLocation.prevMatches=[None for i in range(len(polygonSets))]

    matchingPolygonSet = []

    for setIdx, polygons in enumerate(polygonSets):
        minConfLevel = env["min_conf_levels"][setIdx]

        polygon=None
        if (
            cc in polygons and
            (lat!=0 or long!=0) and
            (
                bestLevel>minConfLevel or
                (
                    bestLevel==minConfLevel and not cc in blackListCountries
                )
            )
        ):  # Search for polygon
            polygon = getPolygon(polygons, lat, long ,cc, processLocation.prevMatches[setIdx])
            processLocation.prevMatches[setIdx] = polygon

            if not polygon:
                sys.stderr.write("Couldn't find polygon in " + env["regions_geojson_files"][setIdx]
                                 + " within " + cc + " where to place location " \
                                 + loc['locid'] + ": " + str(lat) + " " + str(long) + "\n")

        if not polygon:
            unknownPolygons = unknownPolygonSets[setIdx]
            if cc in unknownPolygons and len(unknownPolygons[cc]):
                polygon = unknownPolygons[cc][0]
            elif '??' in unknownPolygons and len(unknownPolygons['??']):
                polygon = unknownPolygons['??'][0]
            else:
                sys.exit("Unable to find unknown polygon for country: " + cc + " in GeoJson file at position " + str(setIdx+1))

        matchingPolygonSet.append(polygon)

    writeRow(loc, matchingPolygonSet)

processLocation.prevMatches=None


def processNetacqLocations(namedPolygonSets, blackListCountries = []):

    def extractUnknownPolygons(polygons):
        # Compile list of unknown/dummy polygons (shape = null) and remove them from main list
        unknownPolygons = {}
        for cc in polygons:
            unknownPolygons[cc] = filter(lambda poly: not poly["shape"] ,polygons[cc])
            polygons[cc] = filter(lambda poly: poly["shape"] ,polygons[cc])
        return unknownPolygons

    polygonSetsNames = [psName for psName, ps in namedPolygonSets]
    polygonSets = [ps for psName,ps in namedPolygonSets]

    unknownPolygonSets = map(extractUnknownPolygons, polygonSets)

    colsToKeep = [
        'locid',
        'edge-latitude',
        'edge-longitude',
        'edge-continent-code',
        'edge-two-letter-country',
        'edge-country',
        'edge-region',
        'edge-region-code',
        'edge-metro-code',
        'edge-city',
        'edge-postal-code',
        'edge-country-conf',
        'edge-region-conf',
        'edge-city-conf',
        'edge-postal-conf'
    ]

    ####

    filePath = env["netacuity_locations_csv_file"]

    sys.stderr.write("reading " + filePath + "\n")

    netacFile = gzip.open(filePath, 'r') if filePath[-3:].lower()=='.gz' else open(filePath, 'r')
    netacReader = csv.reader(netacFile)

    colsIdx = []
    first=True
    for row in netacReader:
        if first: # Grab table header
            first = False

            # Ignore non-existing cols
            colsToKeep = filter(lambda colName: colName in row, colsToKeep)

            colsIdx = map(lambda colName: row.index(colName),colsToKeep)

            sys.stdout.write(','.join(
                ['locid']
                + [
                    (polygonSetsNames[i] or
                        ('polygon'
                            + (('-table'+str(i)) if len(polygonSets)>1 else '')
                        )
                    )
                    + '-id'
                    for i in range(len(polygonSets))
                ]
            ) + "\n")

            continue

        locRecord = {}

        for i, col in enumerate(colsToKeep):
            locRecord[col] = row[colsIdx[i]]

        processLocation(locRecord,polygonSets,unknownPolygonSets,blackListCountries)

    sys.stderr.write("done reading " + filePath + "\n")

########

if __name__ == "__main__":
    processNetacqLocations(getGeoJsonData(), blackListCountries=getBlacklistCountries())
