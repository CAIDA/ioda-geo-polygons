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

import json
import argparse
import sys

PROPERTIES = [
    'id',
    'fqid',
    'name',
    'usercode'
]

env = {}

#######

# CLI syntax

cliParser = argparse.ArgumentParser(description="""
    Generates a table of polygon IDs and properties, based on a GeoJSON. Each polygon in the GeoJson
    must have the following properties: id, name, fqid. If the geojson has a "table-name" top level field,
    the "id" column name will be named "<table-name>-id" instead.
    Table is written to stdout in csv format.
	""")

cliParser.add_argument('-i',  '--geojson_file',
					nargs='?', required=True,
                    help='The path to the GeoJSON file')

env.update(vars(cliParser.parse_args()))

#######

def genPolygonsTable():

    filePath = env["geojson_file"]
    sys.stderr.write("loading " + filePath + "\n")

    with open(filePath) as geoJsonFile:
        geoJson = json.load(geoJsonFile)

    sys.stderr.write("done loading " + filePath + "\n")

    # Write table name in ID column if existing
    colsRename = {}
    if 'table-name' in  geoJson:
        colsRename['id'] = geoJson['table-name'] + '-id'

    sys.stdout.write(','.join(map(
        lambda prop: colsRename[prop] if prop in colsRename else prop,
        PROPERTIES
    )) + "\n")

    for polygon in geoJson['features']:
        sys.stdout.write(','.join(
            map(    # Quote names
                lambda prop: encodeVal(polygon['properties'][prop]).join(['"','"'] if prop == 'name' else ['','']),
                PROPERTIES
            )
        ) + "\n")

def encodeVal(val):
    if val == None:
        return ''
    if isinstance(val, (int, long, float, complex)):
        val = str(val)
    return val.encode('utf-8')

########

if __name__ == "__main__":
    genPolygonsTable()
