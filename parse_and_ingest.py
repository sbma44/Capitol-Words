#!/usr/bin/python

import datetime, sys
from settings import *
from scraper.scraper import run_scraper
from parser.parser import parse_directory
from solr.ingest import solr_ingest_dir

'''
Given a directory, will iterate over all subdirectories, running the parser and
then the ingest script, respectively. Important for manually bringing in bulk
records. '''

if __name__ == '__main__':
    parent_path = sys.argv[1]
    for level in os.walk(parent_path):
        files = level[2]
        thisdir = level[0]
        if len(files) > 0:
            xml_dir = parse_directory(thisdir)
            solr_ingest_dir(xml_dir)


