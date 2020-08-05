import re
from collections import defaultdict
import json
import logging

import requests

from . import conf


def fifa_worldcup():
    source = 'https://raw.githubusercontent.com/lsv/fifa-worldcup-2018/master/data.json'
    resp = requests.get(source)
    return resp.json()


def api_football(config):
    league_id = config['league_id']
    headers = {
        'X-RapidAPI-Key': config['api_token'],
        'X-RapidAPI-Host': 'api-football-v1.p.rapidapi.com'
    }
    url = f'https://api-football-v1.p.rapidapi.com/v2/fixtures/league/{league_id}'
    resp = requests.get(url, headers=headers)
    resp.raise_for_status()
    return resp.json()


def rfpl_2019(config):
    return api_football(config)


def convert_api_season(data):
    teams = {}
    matches = defaultdict(list)
    fixtures = data['api']['fixtures']
    for fix in fixtures:
        for key in ('homeTeam', 'awayTeam'):
            team = fix[key]
            tid = team['team_id']
            teams[tid] = {
                'id': tid,
                'name': team['team_name'],
                'logo': team['logo'],
                'fifaCode': team['team_name'],
                'emojiString': None
            }
        tour = re.search(r'\d+', fix['round']).group()
        matches[tour].append({
            'date': fix['event_date'],
            'name': fix['fixture_id'],
            'type': 'group',
            'home_result': fix['goalsHomeTeam'],
            'away_result': fix['goalsAwayTeam'],
            'home_team': fix['homeTeam']['team_id'],
            'away_team': fix['awayTeam']['team_id'],
            'finished': fix['statusShort'] == 'FT',
            'round': tour,
        })
    data['teams'] = teams.values()
    assert len(data['teams']) == 16
    data['league'] = {
        rnd: {'name': rnd, 'matches': matches}
        for rnd, matches in matches.items()
    }
    return data


def load_fixtures(config):
    data_fpath = conf.get_data_file(config)
    with open(data_fpath) as fp:
        season_data = json.load(fp)
    return convert_api_season(season_data)


def save_rfpl_fixtures(config):
    data = rfpl_2019(config)
    data_fpath = conf.get_data_file(config)
    logging.info(f'Saving fixtures to {data_fpath}')
    with open(data_fpath, 'w') as fp:
        json.dump(data, fp)
