import re
import os
import tempfile
from collections import defaultdict
from datetime import timedelta
import json
import logging

import dateutil.parser
import pytz
import requests

from . import conf, utils

# api-football finished fixture status codes (see fixtures endpoint docs).
FINISHED_STATUSES = {"FT", "AET", "PEN"}
# How long after kickoff to keep polling a match for events. Covers 90' + half
# time + extra time + stoppage and typical kickoff delays.
MATCH_EVENT_WINDOW = timedelta(hours=3)


def _dump_json_atomic(fpath, data):
    """Write JSON so readers never observe a half-written file.

    Both bot containers read these files live from a shared volume, so a
    partial write could be parsed mid-update. Writing to a temp file in the
    same directory and os.replace()-ing is atomic on a single filesystem.
    """
    directory = os.path.dirname(fpath) or "."
    fd, tmp = tempfile.mkstemp(dir=directory, suffix=".tmp")
    try:
        with os.fdopen(fd, "w") as fp:
            json.dump(data, fp)
        os.replace(tmp, fpath)
    except Exception:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def fifa_worldcup():
    source = "https://raw.githubusercontent.com/lsv/fifa-worldcup-2018/master/data.json"
    resp = requests.get(source)
    return resp.json()


def api_football(config, resource_url, query):
    url = f"https://api-football-v1.p.rapidapi.com/v3/{resource_url}"

    headers = {
        "X-RapidAPI-Key": config["api_token"],
        "X-RapidAPI-Host": "api-football-v1.p.rapidapi.com",
    }
    resp = requests.get(url, headers=headers, params=query)
    resp.raise_for_status()
    data = resp.json()
    results = data["results"]
    if not results:
        try:
            error = data["errors"]
        except KeyError:
            error = "RapidAPI error"
        logging.error(f"RapidAPI error: {data}")
        raise ValueError(str(error))
    return data["response"]


def get_teams_info(config):
    with open(config["countries_file"]) as fp:
        data = json.load(fp)
    return {
        c["name"]: {
            "flag": c["flag"]["unicode"],
            "code": c["id"],
        }
        for c in data["teams"]
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
        for key in ("home", "away"):
            team = fix["teams"][key]
            tid = team["id"]
            name = team["name"]
            info = teams_info.get(name)
            code = info["code"] if info else name
            if team["winner"]:
                winner_team = key
            teams[tid] = {
                "id": tid,
                "name": name,
                "logo": team["logo"],
                "fifaCode": code,
                "emojiString": info["flag"] if info else None,
            }
        fix_round = fix["league"]["round"]
        match = {
            "date": fix["fixture"]["date"],
            "name": fix["fixture"]["id"],
            "home_result": fix["goals"]["home"],
            "away_result": fix["goals"]["away"],
            "home_team": fix["teams"]["home"]["id"],
            "away_team": fix["teams"]["away"]["id"],
            "finished": fix["fixture"]["status"]["short"] in ("FT", "AET", "PEN"),
            "round": fix_round,
            "is_playoff": False,
        }
        if "Season" in fix_round:
            tour = re.search(r"\d+", fix_round).group()
            match["type"] = "group"
            match["round"] = tour
            league_matches[tour].append(match)
        elif "Group" in fix_round:
            match["type"] = "group"
            group_matches[fix_round].append(match)
        elif fix_round in (
            "Round of 32",
            "Round of 16",
            "8th Finals",
            "Quarter-finals",
            "Semi-finals",
            "3rd Place Final",
            "Final",
        ):
            match["is_playoff"] = True
            match["home_penalty"] = fix["score"]["penalty"]["home"]
            match["away_penalty"] = fix["score"]["penalty"]["away"]
            match["home_full"] = fix["score"]["fulltime"]["home"]
            match["away_full"] = fix["score"]["fulltime"]["away"]
            match["home_extra"] = fix["score"]["extratime"]["home"]
            match["away_extra"] = fix["score"]["extratime"]["away"]
            match["winner"] = winner_team
            match["type"] = "winner"
            knockout_matches[fix_round].append(match)
        else:
            continue
        if not match["finished"]:
            match["winner"] = None
    converted = {}
    converted["teams"] = teams.values()
    converted["groups"] = {
        rnd: {"name": rnd, "matches": matches} for rnd, matches in group_matches.items()
    }
    converted["knockout"] = {
        rnd: {"name": rnd, "matches": matches}
        for rnd, matches in knockout_matches.items()
    }
    converted["league"] = {
        rnd: {"name": rnd, "matches": matches}
        for rnd, matches in league_matches.items()
    }
    return converted


def load_fixtures(config):
    data_fpath = conf.get_data_file(config, "fixtures")
    with open(data_fpath) as fp:
        season_data = json.load(fp)
    return convert_api_v3(config, season_data)


def save_fixtures(config):
    league_id = config["league_id"]
    season = config.get("season")
    query = {"league": league_id}
    if season:
        query["season"] = season

    data = api_football(config, "fixtures", query)
    data_fpath = conf.get_data_file(config, "fixtures")
    logging.info(f"Saving fixtures to {data_fpath}")
    _dump_json_atomic(data_fpath, data)


def load_update_state(config):
    """Last-run timestamps per resource for the config-driven updater (or {})."""
    data_fpath = conf.get_data_file(config, "update-state")
    try:
        with open(data_fpath) as fp:
            return json.load(fp)
    except (FileNotFoundError, ValueError):
        return {}


def save_update_state(config, state):
    _dump_json_atomic(conf.get_data_file(config, "update-state"), state)


def get_fixture_events(config, fixture_id):
    query = {"fixture": fixture_id}
    try:
        data = api_football(config, "fixtures/events", query)
    except ValueError:
        data = []
    return data


def _load_raw_fixtures(config):
    """Raw api-football fixtures payload saved by save_fixtures (or [])."""
    data_fpath = conf.get_data_file(config, "fixtures")
    try:
        with open(data_fpath) as fp:
            return json.load(fp)
    except (FileNotFoundError, ValueError):
        return []


def load_events(config):
    """Stored events keyed by string fixture id (or {} if none yet).

    This is the shared snapshot both bots read instead of each calling the
    live API. Only the single updater writes it.
    """
    data_fpath = conf.get_data_file(config, "events")
    try:
        with open(data_fpath) as fp:
            return json.load(fp)
    except (FileNotFoundError, ValueError):
        return {}


def get_stored_events(config, fixture_id):
    """Events for one fixture from the shared snapshot (JSON keys are str)."""
    return load_events(config).get(str(fixture_id), [])


def set_fixture_events(config, fixture_id, events):
    """Replace stored events for one fixture in the shared events file.

    Lets the /testEventsFile preview push sample events through the very same
    file the updater writes and both bots read.
    """
    stored = dict(load_events(config))
    stored[str(fixture_id)] = events
    _dump_json_atomic(conf.get_data_file(config, "events"), stored)


def _fixture_start(fix):
    return dateutil.parser.parse(fix["fixture"]["date"]).astimezone(pytz.utc)


def save_events(config):
    """Refresh stored events for matches currently in play, into a shared file.

    A match is "in play" purely by its scheduled kickoff: now is within
    MATCH_EVENT_WINDOW after kickoff. This reads only the local fixtures file
    (the kickoff schedule rarely changes), so the events poll costs ZERO
    fixtures API calls — one events call per in-window match, nothing else.

    Finished matches (per the local fixtures status, refreshed on a slower
    fixtures cron) are skipped early to stop polling before the window ends;
    their last snapshot is kept (merged) for the bot's finish-cycle read.
    """
    now = utils.utcnow()
    events = dict(load_events(config))
    for fix in _load_raw_fixtures(config):
        fixture = fix["fixture"]
        if fixture["status"]["short"] in FINISHED_STATUSES:
            continue
        start = _fixture_start(fix)
        if start <= now <= start + MATCH_EVENT_WINDOW:
            events[str(fixture["id"])] = get_fixture_events(config, fixture["id"])
    data_fpath = conf.get_data_file(config, "events")
    logging.info(f"Saving events to {data_fpath}")
    _dump_json_atomic(data_fpath, events)
