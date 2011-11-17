#!/bin/env python

import argparse
import logging
import logging.handlers
import os.path
import urllib
import urllib2

from BeautifulSoup import BeautifulSoup
from difflib import SequenceMatcher
from tempfile import NamedTemporaryFile
from zipfile import is_zipfile, ZipFile

RAR_ID = bytes("Rar!\x1a\x07\x00")

SUBDIVX_SEARCH_URL = "http://www.subdivx.com/index.php?buscar=%s+%s&accion=5&masdesc=&subtitulos=1&realiza_b=1&oxdown=1"
SUBDIVX_DOWNLOAD_MATCHER = {'name':'a', 'rel':"nofollow", 'target': "new"}

LOGGER_LEVEL = logging.DEBUG
LOGGER_FORMATTER = logging.Formatter('%(asctime)-25s %(levelname)-8s %(name)-29s %(message)s', '%Y-%m-%d %H:%M:%S')

class NoResultsError(Exception):
    pass    


def is_rarfile(fn):
    '''Check quickly whether file is rar archive.'''
    buf = open(fn, "rb").read(len(RAR_ID))
    return buf == RAR_ID

def setup_logger(level):
    global logger
    
    logger = logging.getLogger(__file__[:-3])
    
    logfile = logging.handlers.RotatingFileHandler(logger.name+'.log', maxBytes=1000 * 1024, backupCount=9)
    logfile.setFormatter(LOGGER_FORMATTER)
    logger.addHandler(logfile)
    logger.setLevel(level)

def get_subtitle_url(series_name, series_id, series_quality):
    enc_series_name = urllib.quote(series_name)
    enc_series_id = urllib.quote(series_id)

    logger.debug('Starting request to subdivx.com')
    page = urllib2.urlopen(SUBDIVX_SEARCH_URL % (enc_series_name, enc_series_id))
    logger.debug('Search Query URL: ' + page.geturl())
    page = urllib2.urlopen("http://www.subdivx.com/index.php?buscar=asdad&accion=5&masdesc=&subtitulos=1&realiza_b=1&oxdown=1")
    soup = BeautifulSoup(page)

    results_descriptions = soup('div', id='buscador_detalle_sub')
    
    if not results_descriptions:
        raise(NoResultsError(' '.join(['No suitable subtitles were found for:',
                                      series_name,
                                      series_id,
                                      series_quality])))
        
    search_match = '%s %s %s' % (series_name, series_id, series_quality)
    matcher = SequenceMatcher(lambda x: x==" " or x==".", search_match)

    def calculate_ratio(seq):
        matcher.set_seq2(seq)

        blocks = matcher.get_matching_blocks()
        
        scores = []
        for block in blocks:
            long_start   = block[1] - block[0]
            long_end     = long_start + len(search_match)
            long_substr  = seq[long_start:long_end]

            m2 = SequenceMatcher(None, search_match, long_substr)
            r = m2.ratio()
            if r > .995: return 100
            else: scores.append(r)
    
        return int(100 * max(scores))
    
    best_match = [calculate_ratio(''.join([e for e in description.recursiveChildGenerator() if isinstance(e,unicode)]))
                  for description in results_descriptions]
    
    best_match_index = best_match.index(max(best_match))
    
    return results_descriptions[best_match_index].nextSibling.find(**SUBDIVX_DOWNLOAD_MATCHER)['href']
    
def get_subtitle(url, path):
    in_data = urllib2.urlopen(url)
    temp_file = NamedTemporaryFile()
    
    temp_file.write(in_data.read())
    in_data.close()
    temp_file.seek(0)
    
    if is_zipfile(temp_file.name):
        logger.debug('Unpacking zipped subtitle')

        zip_file = ZipFile(temp_file)
        for name in zip_file.namelist():
            # don't unzip stub __MACOSX folders
            if name.find('.srt') and name.find('__MACOSX') == -1:
                zip_file.extract(name, os.path.dirname(path))

        zip_file.close()
    elif is_rarfile(temp_file.name):
        logger.debug('Saving rared subtitle')
        out_file = open(path + '.rar', 'w')
        out_file.write(temp_file.read())
        temp_file.close()
        out_file.close()

    
if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('path', type=str, help="The series episode identifier to be downloaded")
    parser.add_argument('series_name', type=str, help="The name of the series subs to be downloaded")
    parser.add_argument('series_id', type=str, help="The series episode identifier to be downloaded")
    parser.add_argument('series_quality', type=str, help="The series episode quality to be downloaded")
    parser.add_argument('--quiet', '-q', action='store_true')

    args = parser.parse_args()

    setup_logger(LOGGER_LEVEL)
    
    if not args.quiet:
        console = logging.StreamHandler()
        console.setFormatter(LOGGER_FORMATTER)
        logger.addHandler(console)

    try:
        url = get_subtitle_url(args.series_name, args.series_id, args.series_quality)
    except NoResultsError, e:
        logger.error(e.message)
        raise
    
    out_file_name = '/%s %s %s' % (args.series_name, args.series_id, args.series_quality)
    
    get_subtitle(url, os.path.abspath(args.path) + out_file_name)