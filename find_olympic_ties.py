#!/usr/bin/env python3
import unittest
from tqdm import tqdm
from statistics import mean
import re
from pprint import pprint
import bs4
import requests, requests_cache  # https://requests-cache.readthedocs.io/en/latest/
from selenium import webdriver
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import pickle

options = webdriver.ChromeOptions()
options.add_argument("--headless")
driver = None
timed_sports = ['swimming', 'canoe-sprint', 'marathon-swimming', 'triathlon', 'modern-pentathlon', 'athletics',
                'cycling-mountain-bike', 'cycling-road', 'cycling-bmx-racing', 'canoe-slalom',
                'rowing', 'sailing']
base = 'https://olympics.com'


def get_schedule_by_sport(sport, games='tokyo-2020'):
    '''

    :param sport: sport code (see url pattern on olympics.com or the timed_sport list above
    :param games: defaults to tokyo, again see url pattern for guidance.  Really only works with current games
    :return:
    '''
    global driver
    url = f'{base}/{games}/olympic-games/en/results/{sport}/olympic-schedule-and-results.htm'
    url_atoms = url.split('/')
    try:
        f = open("schedule_cache.p", "rb")
        cache = pickle.load(f)
        f.close()
    except:
        cache = {}
    try:
        page_source = cache[f"{sport}_{games}"]
    except:
        driver = get_driver()
        driver.get(url)
        myElem = WebDriverWait(driver, 25).until(EC.presence_of_element_located((By.CLASS_NAME, 'table-responsive')))
        page_source = driver.page_source
        cache[f"{sport}_{games}"] = page_source
        f = open("schedule_cache.p", "wb")
        pickle.dump(cache, f)
        f.close()
    reuslts = []
    soup = bs4.BeautifulSoup(page_source, 'lxml')
    results = {}
    tablesclasses = ['table table-hover table-schedule']
    for classstr in tablesclasses:
        tables = soup.find_all('table', {'class': "table table-hover table-schedule"})
        if len(tables) > 0:
            break
    if len(tables) == 0:
        print(f"schedule tables not found for {sport}")
        print(url)
        raise
    for it, table in enumerate(tables):
        header = table.find('thead')
        columns = []
        for i, col in enumerate(header.find_all('th')):
            columns.append(col.text.strip().replace('  ', ' '))
        header = table.find('tbody')
        for i, row in enumerate(header.find_all('tr')):
            vals = []
            # print(f"table {it} row {i}")
            data = {'url': None}
            for i, v in enumerate(row.find_all('td')):
                link = v.find('a')
                if link is not None:
                    thisurl = link['href']
                    newurl = _fix_relative_urls(thisurl, url_atoms)
                    if 'freestyle-relay' in newurl:
                        tabno = 2
                    else:
                        tabno = 1
                    data.update({'url': f"{newurl}#result-tab-{tabno}"})
                if "schedule-time" in v['class']:
                    dto = v.find('span', {'class': 'schedule-time-data'})
                    if dto:
                        vals.append(dto['full-date'])
                else:
                    vals.append(v.text.strip().replace('  ', ' '))
            if len(vals) == len(columns):
                data.update(dict(zip(columns, vals)))
                data['Event'] = data['Event'].split("\n")[0]
                # pick appart event title to figure out weather its a heat, semifinal, final etc.
                rstr1 = '([\s\w\',]+)\s(Round [0-9]+)\s,*-*\s*([QualificationPreliminaryRepechageRoundHeatRunQurSmifFnl].*)'
                rstr2 = '([\s\w\',]+) -*\s*([0-9stndQualificationQuarterPreliminaryRoundHeatRepechageRunQuarterfinalSmifFnls].*)'
                rstr3 = '([\s\w\',]+), ([SemiQuarterFfinalsRun\s0-9]+)'
                # rstr4 = '([\s\w\',]+) ([Heats|Repechage|Semifinal|Quarterfinal]+s*) ([1-9stndrdthRun]+)'
                rstr4 = '([\s\w\',]+) ([Heats|Repechage|Semifinal|Quarterfinal]+s*)\s*-*\s*([1-9stndrdthRuniSwim\-Off]+)'
                re1 = re.search(rstr1, data['Event'])
                re2 = re.search(rstr2, data['Event'])
                re3 = re.search(rstr3, data['Event'])
                re4 = re.search(rstr4, data['Event'])
                if re4:
                    hit = 4
                    event = re4.group(1)
                    eventiteration = f"{re4.group(2)} {re4.group(3)}"
                elif re3:
                    hit = 3
                    event = re3.group(1)
                    eventiteration = re3.group(2)
                elif re1:
                    hit = 1
                    event = re1.group(1)
                    eventiteration = f"{re1.group(2)} {re1.group(3)}"
                elif re2:
                    hit = 2
                    event = re2.group(1)
                    eventiteration = re2.group(2)
                    if event.endswith(', Semifinals'):
                        event = event.replace(', Semifinals', '')
                        eventiteration = f"Semifinals {eventiteration}"
                    if event.endswith(', Quarterfinals'):
                        event = event.replace(', Quarterfinals', '')
                        eventiteration = f"Quarterfinals {eventiteration}"
                else:
                    hit = 0
                    event = data['Event']
                    eventiteration = None
                if event not in results.keys():
                    results[event] = {}
                if eventiteration is not None:
                    results[event][eventiteration] = data
                else:
                    results[event] = data
                # print(f"{hit} {event}|{eventiteration}|{data['Event']}")
                # if 'Swim-Off' in data['Event']:
                #     raise
    return results


def get_driver():
    global driver
    if driver is None:
        driver = webdriver.Chrome(options=options, executable_path='/usr/local/bin/chromedriver')
        driver.get(base)
        cookiebutton = WebDriverWait(driver, 25).until(
            EC.presence_of_element_located((By.ID, 'onetrust-accept-btn-handler')))
        cookiebutton.click()
    return driver


def _fix_relative_urls(thisurl, url_atoms):
    dotdots = 0
    while thisurl.startswith('../'):
        dotdots += 1
        thisurl = thisurl.replace('../', '', 1)
    newurl = f"{'/'.join(url_atoms[:-dotdots - 1])}/{thisurl}"
    return newurl


def get_result(url):
    '''
    fetch results l parse results table.
    :param url:
    :return:
    '''
    global driver
    url_atoms = url.split('/')
    cache, page_source = get_page_source("results_cache.p", url)
    soup = bs4.BeautifulSoup(page_source, 'lxml')

    results = {}
    columns = []
    tables = soup.find_all('table', {'class': 'table-result'})

    if len(tables) == 0:
        print(f"{len(tables)} tables {url}")
        jkl = soup.find('div', {'class': 'ResultContentContainer'})
        print(jkl.prettify())
        raise ValueError('results table not found')
    table = tables[-1] # its the last table of that class
    header = table.find('thead')
    for i, col in enumerate(header.find_all('th')):
        columns.append(col.text.strip().replace('  ', ' '))
    body = table.find('tbody')
    for row in body.find_all('tr'):
        vals = []
        for i, cell in enumerate(row.find_all('td')):
            vals.append(cell.text.strip())
        data = dict(zip(columns, vals))
        if 'Team' in data.keys():
            data['Name'] = data['Team']  # normalize team and athelete d
        if 'Name' not in data.keys():
            print(url)
            pprint(data)
            print(row.prettify())
            print(body.prettify())
            raise
        results[data['Name']] = data
    # print(url)
    return results


def get_page_source(cache_file, url):
    global driver
    try:
        f = open(cache_file, "rb")
        cache = pickle.load(f)
        f.close()
    except:
        cache = {}
    try:
        page_source = cache[url]
    except:
        driver = get_driver()
        driver.get(url)
        resultstab = WebDriverWait(driver, 25).until(EC.presence_of_element_located((By.CLASS_NAME, 'nav-link')))

        page_source = driver.page_source
        cache[url] = page_source
        f = open(cache_file, "wb")
        pickle.dump(cache, f)
        f.close()
        print(f"fetched {url}, wrote to {cache_file}")
    return cache, page_source


def get_ties(sport):
    '''
    fetches the event list, then results for each race within each event, produces
    :param sport: sport code
    :return: report in markdown
    '''
    data = get_schedule_by_sport(sport)
    tieornot = {'yes': [], 'no': [], 'tbd': []}
    variance = {'gold-silver': [], 'bronze-4th': []}
    races = 0
    ties = 0
    noties = 0
    lines=[]
    lines.append(f"# {sport}")
    eventlist=tqdm(data.items())
    for event, v in tqdm(data.items()):
        decided = 'no'
        reaction = {'1': 0, '2': 0, '3': 0, '4': 0}
        if 'Final' in v.keys() and v['Final']['Status'] == 'Finished':
            decided = 'yes'
        lines.append(f"### {event}")
        lines.append(f"races: {len(v)}, medals awarded: {decided}")
        times = {}

        for subevent, v2 in v.items():
            if v2['Status'] == "Cancelled":
                continue
            elif v2['Status'] == "Finished":
                results = get_result(v2['url'])
                v2['results'] = results
                for athlete, v3 in results.items():
                    races += 1
                    if v3['Time'] in ['DSQ', 'DNS']:  # disqualfication
                        continue
                    if 'Time' not in v3.keys():
                        print(subevent)
                        pprint(v3)
                        raise
                    if v3['Time'] not in times.keys():
                        times[v3['Time']] = []
                    nameparts = v3['Name'].split(' ')
                    name = ' '.join(nameparts[1:])
                    country = nameparts[0][:3]
                    times[v3['Time']].append(f"{v3['Time']} | {v3['Rank']} | {subevent} | {name} | {country}")
                    if 'Final' in subevent:
                        if 'Team' not in v3.keys():
                            try:
                                reaction[v3['Rank']] = float(v3['ReactionTime'])
                            except:
                                pprint(v3)
                                raise
                        else:
                            reaction = None
            else:
                decided = False
        if not decided:
            tieornot['tbd'].append(event)
        else:
            for time, athletes in times.items():
                if len(athletes) > 1:
                    tieornot['yes'].append(event)

            if event in tieornot['yes']:
                lines.append("\ntime | rank | race | athlete | county")
                lines.append("---- | ---- | ---- | ------- | ------")
                for time, athletes in times.items():
                    if len(athletes) > 1:
                        ties += 1
                        tieornot['yes'].append(event)
                        lines += athletes
            else:
                noties += 1
                tieornot['no'].append(event)
                lines.append(f"   no ties")
            if reaction is not None:
                variance['gold-silver'].append(abs(reaction['2'] - reaction['1']))
                variance['bronze-4th'].append(abs(reaction['4'] - reaction['3']))

        f = open('README.md', 'w')
        f.write("\n".join(lines))
        f.close()

    lines.append("\n## Overall stats")
    lines.append(f"total races {races} completed, races with ties {ties}\n")
    lines.append("total events | events with ties | without ties | not completed yet")
    lines.append(" --- | --- | --- | --- ")
    lines.append(f"{len(set(data.keys()))} | {len(set(tieornot['yes']))} |  {len(set(tieornot['no']))} |  {len(set(tieornot['tbd']))}")
    lines.append(f"reaction time mean variance: gold-silver {mean(variance['gold-silver']):.2f} seconds,  bronze-4th {mean(variance['bronze-4th']):.2f} seconds\n")

    f = open('README.md', 'w')
    f.write("\n".join(lines))
    f.close()
    print('done')

class FiveRingedTestCases(unittest.TestCase):
    def test_schedule(self):
        for sport in timed_sports:
            data = get_schedule_by_sport(sport)
            self.assertGreaterEqual(len(data), 2)

    def test_results(self):
        url = 'https://olympics.com/tokyo-2020/olympic-games/en/results/canoe-slalom/race-results-men-s-canoe-heat-000100-.htm'
        data = get_result(url)
        self.assertEqual(len(data), 18)

        url = 'https://olympics.com/tokyo-2020/olympic-games/en/results/swimming/results-women-s-1500m-freestyle-heat-000100-.htm'
        data = get_result(url)
        self.assertEqual(len(data), 3)

    def test_ties(self):
        get_ties('swimming')


if __name__ == '__main__':
    get_ties('swimming')
