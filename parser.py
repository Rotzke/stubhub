#!/usr/bin/python3.5
"""API parser for StubHub."""
import csv
import json
import logging
import os
import sys
from datetime import datetime
from time import sleep

import requests
from bs4 import BeautifulSoup as bs

logging.basicConfig(format='%(levelname)s: %(message)s', level=logging.INFO)
fieldnames = ['Home Team', 'Date', 'Opponent',
              'Designated Sections', 'Row Filter', 'Quantity Filter']
parser = 'html.parser'


def get_teams():
    """Parse teams list from FBSchedules."""
    URL = 'http://www.fbschedules.com/'
    r = requests.get('{}ncaa/2017-college-football-schedules.php'.format(URL))
    soup = bs(r.text,
              parser).find('div',
                           {'class':
                            """schedu-list headers_"""
                            """left blue_headers"""}).find_all('a')
    with open('input.csv', 'w', newline='') as csvfile:
        writer = csv.DictWriter(csvfile,
                                fieldnames=fieldnames)
        writer.writeheader()
        for i in soup:
            game = {}
            game['Home Team'] = i.text
            logging.info(i.text)
            try:
                for o in bs(requests.get(URL + i['href']).text, parser).\
                    find('table',
                         {'class':
                          'cfb-sch'}).find_all('td',
                                               {'class':
                                                'cfb2'}):
                    if not o.strong.string.lower().startswith(('at', 'off')):
                        game['Opponent'] = o.strong.string.strip()
                        raw_date = o.parent.td.text + str(datetime.now().year)
                        try:
                            date = datetime.strptime(raw_date,
                                                     '%A %b. %d%Y')
                            game['Date'] = datetime.strftime(date, '%Y-%m-%d')
                        except ValueError:
                            game['Date'] = 'N/A'
                            logging.warning('{}: '.format(game['Opponent']) +
                                            'No date available!')
                        writer.writerow(game)
            except AttributeError:
                logging.warning('Possibly is not a game - passing!')


def fill_sheet():
    """Write additional data to sheet."""
    with open('output.csv', 'w', newline='') as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames +
                                ['1st Lowest', '2nd Lowest', '3rd Lowest'])
        writer.writeheader()
        with open('input.csv', 'r') as csvfile:
            reader = csv.DictReader(csvfile, fieldnames=fieldnames)
            for i in [line for line in reader][1:]:
                prices = parse_data(i)['listing']
                if prices[0]['listingPrice']['amount'] != 'N/A':
                    tops = filter_prices(i, prices)
                    i['1st Lowest'] = tops[0]
                    i['2nd Lowest'] = tops[1]
                    i['3rd Lowest'] = tops[2]
                else:
                    i['1st Lowest'] = prices[0]['listingPrice']['amount']
                    i['2nd Lowest'] = prices[1]['listingPrice']['amount']
                    i['3rd Lowest'] = prices[2]['listingPrice']['amount']
                writer.writerow(i)


def parse_data(game):
    """Parse game data from StubHub API."""
    headers = {'Authorization': 'Bearer',
               'Accept': 'application/json',
               'Accept-Encoding': 'application/json'
               }
    query = game['Home Team'] + ' ' + game['Opponent']
    API = 'https://api.stubhub.com/'
    logging.info('Sleep...')
    sleep(14)
    r_id = requests.get("""{}search/catalog/events/v3?"""
                        """name={}&date={}""".format(API, query, game['Date']),
                        headers=headers)
    if r_id.status_code == 403:
        logging.critical('You are not using the US-based IP address!')
        exit(1)
    try:
        event = json.loads(r_id.text)['events'][0]['id']
        r_inv = requests.get("""{}search/inventory/v2?"""
                             """eventid={}""".format(API, event),
                             headers=headers)
        logging.info(game['Home Team'].strip() +
                     ' vs ' + game['Opponent'].strip() + '...OK')
        return(json.loads(r_inv.text))
    except (AttributeError, TypeError):
        logging.critical(game['Home Team'].strip() +
                         ' vs ' + game['Opponent'].strip() + '...FAIL!')
        return({'listing': [{'listingPrice': {'amount': 'N/A'}},
                            {'listingPrice': {'amount': 'N/A'}},
                            {'listingPrice': {'amount': 'N/A'}}]})


def filter_prices(filters, listing):
    """Filter prices data."""
    tops = []
    pure_filters = {}
    count = 0
    if filters['Quantity Filter'].lower() not in ['n/a', 'all', '']:
        if ',' in filters['Quantity Filter']:
            pure_filters['quantity'] =\
                filters['Quantity Filter'].replace(' ', '').split(',')
        else:
            pure_filters['quantity'] = [filters['Quantity Filter']]
    if filters['Designated Sections'].lower() not in ['n/a', 'all', '']:
        if ',' in filters['Designated Sections']:
            pure_filters['sellerSectionName'] =\
                filters['Designated Sections'].replace(' ', '').split(',')
        else:
            pure_filters['sellerSectionName'] =\
                [filters['Designated Sections']]
    if filters['Row Filter'].lower() not in ['n/a', 'all', '']:
        if ',' in filters['Row Filter']:
            pure_filters['row'] =\
                filters['Row Filter'].replace(' ', '').split(',')
        else:
            pure_filters['row'] = [filters['Row Filter']]
    checks = len(pure_filters.keys())
    if checks == 0:
        tops.append(listing[0]['listingPrice']['amount'])
        tops.append(listing[1]['listingPrice']['amount'])
        tops.append(listing[2]['listingPrice']['amount'])
        return tops
    try:
        for i in listing:
            item_checks = 0
            for key in pure_filters.keys():
                if True in [chunk in str(i[key])
                            for chunk in pure_filters[key]]:
                    item_checks += 1
            if item_checks == checks:
                count += 1
                tops.append(i['listingPrice']['amount'])
        if count < 3:
            raise AttributeError
    except (AttributeError, TypeError):
        if len(tops) > 0:
            while len(tops) < 3:
                tops.append('N/A')
            return tops
        return({'listing': [{'listingPrice': {'amount': 'N/A'}},
                            {'listingPrice': {'amount': 'N/A'}},
                            {'listingPrice': {'amount': 'N/A'}}]})
    return tops


def print_menu():
    """Print user menu."""
    print(30 * "-", "MENU", 30 * "-")
    print("1. Generate input list")
    if not os.path.exists('input.csv'):
        print("2. Scrape ticket prices - NO INPUT.CSV FILE FOUND!")
    else:
        print("2. Scrape ticket prices")
    print("3. Exit")
    print(66 * "-")


if __name__ == '__main__':
    while True:
        try:
            print()
            print_menu()
            choice = input("Enter your choice [1-3]: ")
            if choice == '1':
                print()
                get_teams()
            elif choice == '2':
                print()
                if not os.path.exists('input.csv'):
                    print('Please generate/add input.csv file first!')
                    sleep(1)
                    print()
                else:
                    fill_sheet()
            elif choice == '3':
                exit(0)
        except Exception as e:
            exc_type, exc_obj, exc_tb = sys.exc_info()
            logging.critical('{} on line {}'.format(e, str(exc_tb.tb_lineno)))
            input('Press any key to exit...')
            exit(1)
