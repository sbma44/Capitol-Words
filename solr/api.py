#!/usr/bin/python

''' A set of functions that give specific views into the solr documents,
returning nicely formatted statistics.  '''

import urllib, urllib2, sys, os
import settings
try:
    import json
except:
    import simplejson as json

from dateutil.parser import parse as dateparse


# return dicts of dates and frequency counts, plus links back to the raw ascii
# documents

def as_solr_date(datestring):
    ''' converts a string in the form dd/mm/yyyy to a solr date of
    2010-01-01T00:00:00Z'''
    day, month, year = datestring.strip().split('/')
    solr_date = "%s-%s-%sT00:00:00Z" % (year, month, day)
    return solr_date

def encode_and_retrieve(args):
    ''' encode the args and retrieve the solr response.'''
    base_url = os.path.join(settings.SOLR_DOMAIN, 'solr/select?')
    data = urllib.urlencode(args)
    full_url = base_url+data
    print full_url
    fp = urllib2.urlopen(full_url)
    return json.loads(fp.read())

def solr_api_call(args):
    ''' manages the actual API call. adds common query parameters, and handles
    pagination if necessary.'''

    # pagination settings
    if not 'rows' in args:
        rows = 50
        args['rows'] = rows
    else: rows = args['rows']
    if args['rows'] != 0:
        start = 0
        args['start'] = start

    # return results in json format
    args['wt'] = 'json'
    
    # pagination
    responses = []
    if rows != 0:
        while (start == 0 or start < num_found):
            resp = encode_and_retrieve(args)
            responses.append(resp)
            num_found = resp['response']['numFound']
            start = start + rows 
    else:
        resp = encode_and_retrieve(args)
        responses.append(resp)

    return responses

def phrase_over_time(phrase, entity_type=None, entity_value=None, start_date=None, 
    end_date=None, granularity='day', mincount=0, page=1):
    ''' find occurences of a specific phrase over time. returns counts. expects
    date in dd/mm/yyyy format. if 'start' and 'end' date are none, defaults
    to all time. entity information (type and name) limits results to the entity
    specified (eg. occurences of phrase by a single person or party). if entity
    information is empty, then returns results across all entities.  granularity allows an
    interval to be specified over which data will be aggregated and normalized,
    such as by day or by year. default granularity is daily. '''

    args = {}

    if isinstance(start_date, basestring):
        start_date = dateparse(start_date).strftime('%d/%m/%Y')
    if isinstance(end_date, basestring):
        end_date = dateparse(end_date).strftime('%d/%m/%Y')
    
    # set up the faceting. 

    args['facet'] = "true"
    args['facet.date'] = 'date'
    args['facet.field'] = 'date'

    # Limit number of results to 100 at a time.
    args['facet.limit'] = 100
    args['facet.offset'] = int(page) * 100
    args['facet.sort'] = 'false'

    if start_date and end_date:
        date_start_value = as_solr_date(start_date)
        date_end_value = as_solr_date(end_date) 
    else:
        # default date range is all time
        date_start_value = as_solr_date(settings.OLDEST_DATE)
        date_end_value = 'NOW/DAY+1DAY'
    args['facet.date.start'] = date_start_value
    args['facet.date.end'] =   date_end_value
    
    # specify facet granularity
    if granularity == 'year':
        date_gap_value = '+1YEARS'
    elif granularity == 'month':
        date_gap_value = '+1MONTHS'
    elif granularity == 'week':
        date_gap_value = '+7DAYS'
    elif granularity == 'congress':
        # XXX get start and end dates of current and past congresses to fill these in
        pass
    else:
        date_gap_value = '+1DAY'
    args['facet.date.gap'] = date_gap_value

    # specify actual search parameters, including limiting by entity if
    # specified. if entity_type and entity_value are specified, then the search
    # is limited to that specific entity.  
    if entity_type and entity_value:
        if entity_type == 'state':
            field_name = 'speaker_state'
        if entity_type == 'party':
            field_name = 'speaker_party'
        if entity_type == 'legislator':
            field_name = 'speaker'
        if entity_type == 'bioguide':
            field_name = 'speaker_bioguide'
        field_value = entity_value
        q = '''%s:"%s" AND text:"%s"''' % (field_name, field_value, phrase)
    else:
        q = '''text:"%s"''' % (phrase)
    args['q'] = q 

    # return counts only, not the documents themselves
    args['rows'] = 0

    # do the api call
    json_resp = solr_api_call(args)

    # remove any cruft and format nicely. 
    return json_resp

def phrase_by_category(phrase, entity_type, start_date=None, end_date=None, mincount=1, sort='false'):
    '''finds occurences of a specific phrase by entity_type. expects
    dates in dd/mm/yyyy format. if 'start' and 'end' date are none, defaults
    to all time. the mincount argument controls whether counts are returned for all
    entities in the category, or only those with non-zero results.''' 
    args = {}

    if isinstance(start_date, basestring):
        start_date = dateparse(start_date).strftime('%d/%m/%Y')
    if isinstance(end_date, basestring):
        end_date = dateparse(end_date).strftime('%d/%m/%Y')
    
    # set up the faceting. many of these query args need to be set using a
    # string variable for the key since they contain periods. 

    args['facet'] = "true"
    if entity_type == 'legislator':
        field = 'speaker_bioguide'
    elif entity_type == 'state':
        field = 'speaker_state'
    elif entity_type == 'party':
        field = 'speaker_party'
    elif entity_type == 'bioguide':
        field = 'speaker_bioguide'
    else:
        raise NotImplementedError(entity_type)
    args['facet.field'] = field

    if mincount:
        args['facet.mincount'] = 1

    args['facet.sort'] = sort

    # default limit for # faceted fields returned is 100; we want to return for
    # all fields. 
    facet_limit = 'facet.limit'
    args[facet_limit] = -1

    q = '''text:"%s"''' % phrase
    if start_date and end_date:
        start = as_solr_date(start_date)
        end = as_solr_date(end_date)
        daterange = '''date:[%s TO %s]''' % (start, end)
        q = '''(%s AND %s)''' % (q, daterange)
    args['q'] = q 

    # return counts only, not the documents themselves
    args['rows'] = 0

    # do the api call
    json_resp = solr_api_call(args)

    # remove any cruft and format nicely. 
    return json_resp


def most_frequent_phrases(n=1, start_date=None, end_date=None, entity_type=None, 
    entity_name=None, page=1):

    if isinstance(start_date, basestring):
        start_date = dateparse(start_date).strftime('%d/%m/%Y')
    if isinstance(end_date, basestring):
        end_date = dateparse(end_date).strftime('%d/%m/%Y')
    if isinstance(n, basestring):
        n = int(n)

    args = {}
    
    args['facet'] = 'true'
    args['facet.mincount'] = 1
    args['facet.method'] = 'enum'
    # return counts only, not the documents themselves
    args['rows'] = 0
    if n == 1:
        args['facet.field'] = 'text'
    elif n == 2:
        args['facet.field'] = 'bigrams'
    elif n == 3:
        args['facet.field'] = 'trigrams'
    elif n == 4:
        args['facet.field'] = 'quadgrams'
    elif n == 5:
        args['facet.field'] = 'pentagrams'

    args['facet.limit'] = 100
    args['facet.offset'] = int(page) * 100
    args['facet.sort'] = 'count'
 
    if start_date and end_date:
        start = as_solr_date(start_date)
        end = as_solr_date(end_date)
        q = '''date:[%s TO %s]''' % (start, end)
        args['q'] = q
     
    if entity_type and entity_name:
        if entity_type == 'state':
            field_name = 'speaker_state'
        if entity_type == 'party':
            field_name = 'speaker_party'
        if entity_type == 'legislator':
            field_name = 'speaker'
        if entity_type == 'bioguide':
            field_name = 'speaker_bioguide'
        entity_constraint = '''%s:%s''' % (field_name, entity_name)
        if 'q' in args:
            # then we've already set the date above, so combine it with the
            # entity constraint. 
            args['q'] = '''(%s AND %s)''' % (entity_constraint, args['q'])
        else:
            args['q'] = entity_constraint  
    if 'q' not in args:
        # at this point if neither of the above constraints have been set, then
        # use a wildcard search
        args['q'] = "*:*"     

    # do the api call
    json_resp = solr_api_call(args)

    # remove any cruft and format nicely. 
    return json_resp

