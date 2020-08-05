import os


def get_data_file(config):
    lid = config['league_id']
    data_dir = config['data_dir']
    return os.path.join(data_dir, f'fixtures-{lid}.json')


def get_db_file(config):
    return os.path.join(config['data_dir'], f'base-{config["league_id"]}.sqlite')


def get_results_file(config):
    return os.path.join(config['data_dir'], f'results-{config["league_id"]}.json')
