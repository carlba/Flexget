from __future__ import unicode_literals, division, absolute_import
import logging
import re
import feedparser
import math
from flexget import plugin
from flexget.event import event
from flexget.utils.imdb import extract_id
from flexget.utils.cached_input import cached
from flexget.entry import Entry
from flexget.utils.soup import get_soup

log = logging.getLogger('imdb_list')
USER_ID_RE = r'^ur\d{7,8}$'

class ImdbList(object):
    """"Creates an entry for each movie in your imdb list."""

    schema = {
        'type': 'object',
        'properties': {
            'user_id': {
                'type': 'string',
                'pattern': USER_ID_RE,
                'error_pattern': 'user_id must be in the form urXXXXXXX'
            },
            'list': {'type': 'string'}
        },
        'required': ['list', 'user_id'],
        'additionalProperties': False
    }

    @cached('imdb_list', persist='2 hours')
    def on_task_input(self, task, config):
        # Create movie entries by parsing imdb list page(s) html using beautifulsoup

        log.verbose('Retrieving list %s ...' % config['list'])

        if config['list'] in ['watchlist', 'ratings', 'checkins']:
            url = 'http://www.imdb.com/user/%s/%s' % (config['user_id'], config['list']) + '?view=compact'
        else:
            url = 'http://rss.imdb.com/list/%s' % config['list'] + '?view=compact'

        log.debug('Requesting %s' % url)
        page = task.requests.get(url)
        if page.status_code != 200:
            raise plugin.PluginError('Unable to get imdb list. Either list is private or does not exist.')

        soup = get_soup(page.text)
        div = soup.find('div',{'id':'root'})
        soup = get_soup(str(div))
        div = soup.find('div',class_='desc')

        if not div:
            log.verbose('No movies were found in imdb list.')
            return

        total_movie_count = int(div.get('data-size'))
        number_of_pages = math.ceil(total_movie_count/250)

        current_page = 1
        entries = []
        while current_page <= number_of_pages:
            if current_page > 1:
                log.debug('Requesting page: %s of imdb list' % current_page)
                start = current_page * 250 - 250 + 1
                page = task.requests.get(url + '&start=' + str(start))
                if page.status_code != 200:
                    raise plugin.PluginError('Unable to get page: %s of imdb list' % current_page)

            soup = get_soup(page.text)
            div = soup.find('div',{'id':'root'})
            soup = get_soup(str(div))
            divs = soup.find_all('td',class_='title')
            soup = get_soup(str(divs))
            links = soup.find_all('a')
            for a in links:
                    link = 'http://www.imdb.com' + a.get('href')
                    entry = Entry()
                    entry['title'] = a.string
                    entry['url'] = link
                    entry['imdb_id'] = extract_id(link)
                    entry['imdb_name'] = a.string
                    entries.append(entry)

            current_page = current_page + 1

        return entries

@event('plugin.register')
def register_plugin():
    plugin.register(ImdbList, 'imdb_list', api_ver=2)
