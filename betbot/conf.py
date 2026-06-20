import os


def get_shared_dir(config):
    """Directory for match data shared between bots: fixtures and events.

    A single updater dumps these here and every bot reads them, so the data is
    fetched from the API once regardless of how many bots run. Falls back to
    data_dir when ``shared_dir`` isn't configured (single-bot setups).
    """
    return config.get("shared_dir", config["data_dir"])


def get_data_file(config, resource):
    lid = config["league_id"]
    season = config.get("season", "no")
    return os.path.join(get_shared_dir(config), f"{resource}-{lid}-{season}.json")


def _make_group_name(config):
    return f"{config['league_id']}-{config['season']}-{config['group_id']}"


def get_db_file(config):
    return os.path.join(config["data_dir"], f"base-{_make_group_name(config)}.sqlite")


def get_results_file(config):
    return os.path.join(config["data_dir"], f"results-{_make_group_name(config)}.json")


def get_chart_race_file(config):
    return os.path.join(
        config["data_dir"], f"chart-race-{_make_group_name(config)}.mp4"
    )
