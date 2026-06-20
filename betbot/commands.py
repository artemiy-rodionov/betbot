import logging
import json
from datetime import timedelta

import dateutil.parser

from config import config

from . import sources, database, utils


def dump_info():
    db = database.Database(config)
    print(str(db.teams))
    print(str(db.matches))


def dump_results(results_date):
    db = database.Database(config)
    if results_date is not None:
        print(
            json.dumps(
                db.predictions.genResults(results_date), indent=2, sort_keys=True
            )
        )


def update_fixtures():
    logging.info("Updating fixtures")
    sources.save_fixtures(config)


def update_events():
    logging.info("Updating events")
    sources.save_events(config)


# Resource name (as used in config["update_intervals"]) -> updater function.
_RESOURCE_UPDATERS = {
    "fixtures": sources.save_fixtures,
    "events": sources.save_events,
}


def update_all(cfg=config):
    """Single config-driven updater: refresh each resource that is due.

    ``cfg["update_intervals"]`` maps a resource to the minimum minutes between
    API refreshes, e.g. ``{"fixtures": 15, "events": 3}``. One cron tick runs
    this; a small state file in the shared dir records the last run per
    resource so each is throttled independently against a single schedule.
    Resources absent from the config (or with a falsy interval) are never
    fetched — that is how you opt a resource out.
    """
    intervals = cfg.get("update_intervals", {}) or {}
    now = utils.utcnow()
    state = sources.load_update_state(cfg)
    changed = False
    for resource, minutes in intervals.items():
        updater = _RESOURCE_UPDATERS.get(resource)
        if updater is None or not minutes:
            logging.warning("No updater for resource %r; skipping", resource)
            continue
        last = state.get(resource)
        due = (
            last is None
            or dateutil.parser.parse(last) + timedelta(minutes=minutes) <= now
        )
        if due:
            logging.info("Updating %s", resource)
            updater(cfg)
            state[resource] = now.isoformat()
            changed = True
    if changed:
        sources.save_update_state(cfg, state)
