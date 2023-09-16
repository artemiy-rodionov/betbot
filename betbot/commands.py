import logging
import json

from config import config

from . import sources, database


def dump_info():
    db = database.Database(config)
    print(str(db.teams))
    print(str(db.matches))


def dump_results(results_date):
    db = database.Database(config)
    if results_date is not None:
        print(json.dumps(db.predictions.genResults(results_date), indent=2, sort_keys=True))


def update_fixtures():
    logging.info('Updating fixtures')
    sources.save_fixtures(config)


def update_standings():
    logging.info('Updating standings')
    sources.save_standings(config)
