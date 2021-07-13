import os


def get_data_file(config):
    lid = config['league_id']
    season = config.get('season', 'no')
    data_dir = config['data_dir']
    return os.path.join(data_dir, f'fixtures-{lid}-{season}.json')


def _make_group_name(config):
    return f'{config["league_id"]}-{config["season"]}-{config["group_id"]}'


def get_db_file(config):
    return os.path.join(
        config['data_dir'],
        f'base-{_make_group_name(config)}.sqlite'
    )


def get_results_file(config):
    return os.path.join(config['data_dir'], f'results-{_make_group_name(config)}.json')


def get_chart_race_file(config):
    return os.path.join(config['data_dir'], f'chart-race-{_make_group_name(config)}.mp4')
