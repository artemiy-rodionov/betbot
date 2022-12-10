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


def get_teams_info(config):
    with open(config['countries_file']) as fp:
        data = json.load(fp)
    return {
        c['name']: {
            'flag': c['flag']['unicode'],
            'code': c['id'],
        }
        for c in data['teams']
    }


def convert_api_v3(config, data):
    """V3 converter for uefa cup"""
    teams = {}
    league_matches = defaultdict(list)
    group_matches = defaultdict(list)
    knockout_matches = defaultdict(list)
    fixtures = data
    try:
        teams_info = get_teams_info(config)
    except Exception:
        teams_info = {}
    for fix in fixtures:
        winner_team = None
        for key in ('home', 'away'):
            team = fix['teams'][key]
            tid = team['id']
            name = team['name']
            info = teams_info.get(name)
            code = info['code'] if info else name
            if team['winner']:
                winner_team = key
            teams[tid] = {
                'id': tid,
                'name': name,
                'logo': team['logo'],
                'fifaCode': code,
                'emojiString': info['flag'] if info else None,
            }
        fix_round = fix['league']['round']
        match = {
            'date': fix['fixture']['date'],
            'name': fix['fixture']['id'],
            'home_result': fix['goals']['home'],
            'away_result': fix['goals']['away'],
            'home_team': fix['teams']['home']['id'],
            'away_team': fix['teams']['away']['id'],
            'finished': fix['fixture']['status']['short'] in ('FT', 'AET', 'PEN'),
            'round': fix_round,
            'is_playoff': False,
        }
        if 'Season' in fix_round:
            tour = re.search(r'\d+', fix_round).group()
            match['type'] = 'group'
            match['round'] = tour
            league_matches[tour].append(match)
        elif 'Group' in fix_round:
            match['type'] = 'group'
            group_matches[fix_round].append(match)
        elif fix_round in (
            'Round of 16',
            '8th Finals',
            'Quarter-finals',
            'Semi-finals',
            'Final'
        ):
            match['is_playoff'] = True
            match['home_penalty'] = fix['score']['penalty']['home']
            match['away_penalty'] = fix['score']['penalty']['away']
            match['home_full'] = fix['score']['fulltime']['home']
            match['away_full'] = fix['score']['fulltime']['away']
            match['home_extra'] = fix['score']['extratime']['home']
            match['away_extra'] = fix['score']['extratime']['away']
            match['winner'] = winner_team
            match['type'] = 'winner'
            knockout_matches[fix_round].append(match)
        else:
            continue
        if not match['finished']:
            match['winner'] = None
    converted = {}
    converted['teams'] = teams.values()
    converted['groups'] = {
        rnd: {'name': rnd, 'matches': matches}
        for rnd, matches in group_matches.items()
    }
    converted['knockout'] = {
        rnd: {'name': rnd, 'matches': matches}
        for rnd, matches in knockout_matches.items()
    }
    converted['league'] = {
        rnd: {'name': rnd, 'matches': matches}
        for rnd, matches in league_matches.items()
    }
    return converted


def load_fixtures(config):
    data_fpath = conf.get_data_file(config)
    with open(data_fpath) as fp:
        season_data = json.load(fp)
    return convert_api_v3(config, season_data)


def save_fixtures(config):
    data = api_football(config)
    data_fpath = conf.get_data_file(config)
    logging.info(f'Saving fixtures to {data_fpath}')
    with open(data_fpath, 'w') as fp:
        json.dump(data, fp)
