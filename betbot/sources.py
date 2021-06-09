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
    season = config.get('season')

    url = 'https://api-football-v1.p.rapidapi.com/v3/fixtures'

    headers = {
        'X-RapidAPI-Key': config['api_token'],
        'X-RapidAPI-Host': 'api-football-v1.p.rapidapi.com'
    }
    query = {
        'league': league_id
    }
    if season:
        query['season'] = season
    resp = requests.get(url, headers=headers, params=query)
    resp.raise_for_status()
    data = resp.json()
    results = data['results']
    if not results:
        try:
            error = data['errors']
        except KeyError:
            error = 'RapidAPI error'
        logging.error(f'RapidAPI error: {data}')
        raise ValueError(str(error))
    return data['response']


def convert_api_v2_season(data):
    """Deprecated rapidapi v2 converter for rfpl season"""
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


def get_teams_info(config):
    with open(config['uefa_2020_file']) as fp:
        data = json.load(fp)
    return {
        c['name']: {
            'flag': c['flag']['unicode'],
            'code': c['id'],
        }
        for c in data['teams']
    }


def convert_api_v3_cup(config, data):
    """V3 converter for uefa cup"""
    teams = {}
    group_matches = defaultdict(list)
    knockout_matches = defaultdict(list)
    fixtures = data
    try:
        teams_info = get_teams_info(config)
    except Exception:
        teams_info = {}
    for fix in fixtures:
        for key in ('home', 'away'):
            team = fix['teams'][key]
            tid = team['id']
            name = team['name']
            info = teams_info.get(name)
            code = info['code'] if info else name
            teams[tid] = {
                'id': tid,
                'name': name,
                'logo': team['logo'],
                'fifaCode': code,
                'emojiString': info['flag'] if info else None,
            }
        fix_round = fix['league']['round']
        if 'Group' not in fix_round:
            continue
        match = {
            'date': fix['fixture']['date'],
            'name': fix['fixture']['id'],
            'home_result': fix['goals']['home'],
            'away_result': fix['goals']['away'],
            'home_team': fix['teams']['home']['id'],
            'away_team': fix['teams']['away']['id'],
            'finished': fix['fixture']['status']['short'] == 'FT',
            'type': 'group',
            'round': fix_round,
        }
        group_matches[fix_round].append(match)
    converted = {}
    converted['teams'] = teams.values()
    converted['groups'] = {
        rnd: {'name': rnd, 'matches': matches}
        for rnd, matches in group_matches.items()
    }
    converted['knockout'] = knockout_matches
    return converted


def load_fixtures(config):
    data_fpath = conf.get_data_file(config)
    with open(data_fpath) as fp:
        season_data = json.load(fp)
    return convert_api_v3_cup(config, season_data)


def save_fixtures(config):
    data = api_football(config)
    data_fpath = conf.get_data_file(config)
    logging.info(f'Saving fixtures to {data_fpath}')
    with open(data_fpath, 'w') as fp:
        json.dump(data, fp)
