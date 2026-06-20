import datetime
import json
from collections import namedtuple

import pytest
import pytz

from betbot import conf, database, helpers, messages, sources

FakeUser = namedtuple("FakeUser", ["id", "first_name", "last_name", "username"])

MATCH_DATA = {
    "teams": [
        {
            "id": f"Team{num}",
            "name": "Team",
            "fifaCode": "",
            "emojiString": "",
            "logo": "",
        }
        for num in range(1, 10)
    ],
    "groups": {
        "rnd1": {
            "name": "rnd1",
            "matches": [
                {
                    "date": "2022-06-01T00:00:00",
                    "name": "group_1-0",
                    "home_result": 1,
                    "away_result": 0,
                    "home_team": "Team1",
                    "away_team": "Team2",
                    "finished": "FT",
                    "round": "Group",
                    "type": "group",
                    "is_playoff": False,
                },
                {
                    "date": "2022-07-01T00:00:00",
                    "name": "group_1-1",
                    "home_result": 1,
                    "away_result": 1,
                    "home_team": "Team3",
                    "away_team": "Team4",
                    "finished": "FT",
                    "round": "Group",
                    "type": "group",
                    "is_playoff": False,
                },
            ],
        }
    },
    "knockout": {
        "Final": {
            "name": "Final",
            "matches": [
                {
                    "date": "2022-07-01T00:00:00",
                    "name": "playoff_1-0",
                    "home_result": 1,
                    "away_result": 0,
                    "winner": "home",
                    "home_team": "Team3",
                    "away_team": "Team4",
                    "finished": "FT",
                    "round": "Final",
                    "type": "winner",
                    "is_playoff": True,
                    "home_penalty": None,
                    "away_penalty": None,
                    "home_full": 1,
                    "away_full": 0,
                    "home_extra": None,
                    "away_extra": None,
                },
                {
                    "date": "2022-07-01T00:00:00",
                    "name": "playoff_1-1penalty",
                    "home_result": 1,
                    "away_result": 1,
                    "winner": "home",
                    "home_team": "Team3",
                    "away_team": "Team4",
                    "finished": "FT",
                    "round": "Final",
                    "type": "winner",
                    "is_playoff": True,
                    "home_penalty": 6,
                    "away_penalty": 5,
                    "home_full": 1,
                    "away_full": 1,
                    "home_extra": 1,
                    "away_extra": 1,
                },
                {
                    "date": "2022-07-01T00:00:00",
                    "name": "playoff_1-1extra",
                    "home_result": 2,
                    "away_result": 1,
                    "winner": "home",
                    "home_team": "Team3",
                    "away_team": "Team4",
                    "finished": "FT",
                    "round": "Final",
                    "type": "winner",
                    "is_playoff": True,
                    "home_penalty": None,
                    "away_penalty": None,
                    "home_full": 1,
                    "away_full": 1,
                    "home_extra": 2,
                    "away_extra": 1,
                },
            ],
        }
    },
}

TEAMS = database.Teams(MATCH_DATA)


def test_group_scores(monkeypatch):
    monkeypatch.setattr(database, "SCORE_MODE", "default")
    matches = database.Matches(MATCH_DATA, TEAMS)
    result_win = matches.getMatch("group_1-0").result()
    assert result_win.score(database.Result(0, 0)) == 0
    assert result_win.score(database.Result(0, 1)) == 0
    assert result_win.score(database.Result(3, 0)) == 1
    assert result_win.score(database.Result(2, 0)) == 1
    assert result_win.score(database.Result(2, 1)) == 2
    assert result_win.score(database.Result(1, 0)) == 3

    result_draw = matches.getMatch("group_1-1").result()
    assert result_draw.score(database.Result(3, 0)) == 0
    assert result_draw.score(database.Result(0, 1)) == 0
    assert result_draw.score(database.Result(0, 0)) == 2
    assert result_draw.score(database.Result(1, 1)) == 3
    assert result_draw.score(database.Result(2, 2)) == 2


def test_playoff_score_default(monkeypatch):
    monkeypatch.setattr(database, "SCORE_MODE", "default")
    monkeypatch.setattr(database, "EXTRA_SCORE_MODE", "default")
    matches = database.Matches(MATCH_DATA, TEAMS)

    result_win = matches.getMatch("playoff_1-0").result()
    assert result_win.score(database.Result(0, 0, 1)) == 1
    assert result_win.score(database.Result(1, 1, 1)) == 1
    assert result_win.score(database.Result(0, 0, 2)) == 0
    assert result_win.score(database.Result(0, 1)) == 0
    assert result_win.score(database.Result(3, 0)) == 1
    assert result_win.score(database.Result(2, 1)) == 2
    assert result_win.score(database.Result(1, 0)) == 3

    result_extra = matches.getMatch("playoff_1-1extra").result()
    assert result_extra.score(database.Result(2, 1)) == 3
    assert result_extra.score(database.Result(1, 0)) == 2
    assert result_extra.score(database.Result(2, 0)) == 1
    assert result_extra.score(database.Result(0, 1)) == 0
    assert result_extra.score(database.Result(0, 0, 1)) == 1
    assert result_extra.score(database.Result(0, 0, 2)) == 0
    assert result_extra.score(database.Result(1, 1, 1)) == 1
    assert result_extra.score(database.Result(1, 1, 2)) == 0

    result_penalty = matches.getMatch("playoff_1-1penalty").result()
    assert result_penalty.score(database.Result(1, 0)) == 1
    assert result_penalty.score(database.Result(2, 0)) == 1
    assert result_penalty.score(database.Result(0, 1)) == 0
    assert result_penalty.score(database.Result(0, 0, 1)) == 3
    assert result_penalty.score(database.Result(0, 0, 2)) == 2
    assert result_penalty.score(database.Result(1, 1, 1)) == 4
    assert result_penalty.score(database.Result(1, 1, 2)) == 3


def test_playoff_score_extra(monkeypatch):
    monkeypatch.setattr(database, "SCORE_MODE", "default")
    monkeypatch.setattr(database, "EXTRA_SCORE_MODE", "extratime")
    matches = database.Matches(MATCH_DATA, TEAMS)

    # Вроде договорили что так же, и учитывается только основное время.
    # Если же ставишь на ничью, то так же выбираешь победителя, и за угаданного победителя в доп время +1балл
    result_win = matches.getMatch("playoff_1-0").result()
    assert result_win.score(database.Result(0, 0, 1)) == 1
    assert result_win.score(database.Result(1, 1, 1)) == 1
    assert result_win.score(database.Result(0, 0, 2)) == 0
    assert result_win.score(database.Result(0, 1)) == 0
    assert result_win.score(database.Result(3, 0)) == 1
    assert result_win.score(database.Result(2, 1)) == 2
    assert result_win.score(database.Result(1, 0)) == 3

    # Счёт 1-1 победа первой команды в доп время или в серии пенальти
    result_extra = matches.getMatch("playoff_1-1extra").result()
    # Тот кто поставил на победу второй команды получает 1 балл
    assert result_extra.score(database.Result(1, 0)) == 1
    assert result_extra.score(database.Result(2, 0)) == 1
    # Тот кто поставил на победу второй команды не получает ничего
    assert result_extra.score(database.Result(0, 1)) == 0
    # 0-0(2-2,3-3..) и победа первой команды получает 3 балла
    assert result_extra.score(database.Result(0, 0, 1)) == 3
    # Тот кто поставил на 0-0(2-2,3-3..) и победа второй команды получает 2 балла
    assert result_extra.score(database.Result(0, 0, 2)) == 2
    # 1-1 победа первой команды 4 балла
    assert result_extra.score(database.Result(1, 1, 1)) == 4
    # 1-1 победа второй команды 3 балла
    assert result_extra.score(database.Result(1, 1, 2)) == 3

    result_penalty = matches.getMatch("playoff_1-1penalty").result()
    # Тот кто поставил на победу второй команды получает 1 балл
    assert result_penalty.score(database.Result(1, 0)) == 1
    assert result_penalty.score(database.Result(2, 0)) == 1
    # Тот кто поставил на победу второй команды не получает ничего
    assert result_penalty.score(database.Result(0, 1)) == 0
    # 0-0(2-2,3-3..) и победа первой команды получает 3 балла
    assert result_penalty.score(database.Result(0, 0, 1)) == 3
    # Тот кто поставил на 0-0(2-2,3-3..) и победа второй команды получает 2 балла
    assert result_penalty.score(database.Result(0, 0, 2)) == 2
    # 1-1 победа первой команды 4 балла
    assert result_penalty.score(database.Result(1, 1, 1)) == 4
    # 1-1 победа второй команды 3 балла
    assert result_penalty.score(database.Result(1, 1, 2)) == 3


def test_pending_requests_crud(tmp_path):
    db_path = str(tmp_path / "base.sqlite")
    pending = database.PendingRequests(db_path)
    user = FakeUser(id=42, first_name="Ann", last_name="Lee", username="ann")

    assert not pending.isPending(42)
    assert pending.getRequest(42) is None

    pending.addRequest(user, database.utcnow())
    assert pending.isPending(42)
    req = pending.getRequest(42)
    assert req.id() == 42
    assert req.name() == "Ann Lee"
    assert req.username() == "ann"
    assert [r.id() for r in pending.listRequests()] == [42]

    # Re-requesting is idempotent (no duplicate rows).
    pending.addRequest(user, database.utcnow())
    assert len(pending.listRequests()) == 1

    pending.removeRequest(42)
    assert not pending.isPending(42)
    assert pending.listRequests() == []


def test_pending_request_name_fallback(tmp_path):
    pending = database.PendingRequests(str(tmp_path / "base.sqlite"))
    pending.addRequest(
        FakeUser(id=7, first_name=None, last_name=None, username=None),
        database.utcnow(),
    )
    assert pending.getRequest(7).name() == "<id: 7>"


def test_change_name_reflected_in_player(tmp_path):
    db_path = str(tmp_path / "base.sqlite")
    players = database.Players(db_path, admin_id=1)
    players.createPlayer(99, "John", "Doe")

    assert players.getPlayer(99).name() == "John Doe"

    players.changeName(99, "Johnny")
    assert players.getPlayer(99).name() == "Johnny"
    # short_name still falls back to first_name.
    assert players.getPlayer(99).short_name() == "John"


def test_create_queens_page(tmp_path):
    db_path = str(tmp_path / "base.sqlite")
    players = database.Players(db_path, admin_id=1)
    players.createPlayer(10, "Zoe", None, is_queen=True)
    players.createPlayer(11, "Amy", None, is_queen=False)
    players.createPlayer(-999, "Bot", "Bot", is_bot=True)  # bots excluded

    class DB:
        pass

    db = DB()
    db.players = players

    text, keyboard = helpers.create_queens_page(db)
    rows = keyboard.keyboard  # list of rows, each a list of buttons
    labels = [btn.text for row in rows for btn in row]
    cbs = [btn.callback_data for row in rows for btn in row]

    # Bot excluded -> only 2 buttons, sorted by name (Amy before Zoe).
    assert len(labels) == 2
    assert labels[0].endswith("Amy") and labels[1].endswith("Zoe")
    # Amy is not queen -> tapping makes queen (target 1); Zoe is queen -> target 0.
    assert cbs[0] == "queen_1_11"
    assert cbs[1] == "queen_0_10"
    assert "♛" in labels[1]  # queen marker shown for Zoe


def test_create_queens_page_empty(tmp_path):
    players = database.Players(str(tmp_path / "base.sqlite"), admin_id=1)

    class DB:
        pass

    db = DB()
    db.players = players
    assert helpers.create_queens_page(db) is None


def test_clean_display_name():
    assert helpers.clean_display_name("  Bob  Smith ") == ("Bob Smith", None)
    # Markdown control chars stripped.
    assert helpers.clean_display_name("*Bob*") == ("Bob", None)

    name, err = helpers.clean_display_name("   ")
    assert name is None and err == messages.NAME_EMPTY

    name, err = helpers.clean_display_name("x" * (helpers.MAX_NAME_LEN + 1))
    assert name is None and err == messages.NAME_TOO_LONG % helpers.MAX_NAME_LEN


@pytest.mark.parametrize(
    "players, expected",
    [
        # No ties: sequential ranks.
        (
            [
                {"id": 1, "sort_key": (10, 3)},
                {"id": 2, "sort_key": (7, 1)},
                {"id": 3, "sort_key": (4, 0)},
            ],
            {1: 1, 2: 2, 3: 3},
        ),
        # Players 2 and 3 tied -> both rank 2; next player jumps to rank 4.
        (
            [
                {"id": 1, "sort_key": (10, 3)},
                {"id": 2, "sort_key": (7, 1)},
                {"id": 3, "sort_key": (7, 1)},
                {"id": 4, "sort_key": (4, 0)},
            ],
            {1: 1, 2: 2, 3: 2, 4: 4},
        ),
        # Equal score but different exact_score -> distinct ranks.
        (
            [
                {"id": 1, "sort_key": (7, 2)},
                {"id": 2, "sort_key": (7, 1)},
            ],
            {1: 1, 2: 2},
        ),
        # Everyone tied -> all rank 1.
        (
            [
                {"id": 1, "sort_key": (5, 0)},
                {"id": 2, "sort_key": (5, 0)},
                {"id": 3, "sort_key": (5, 0)},
            ],
            {1: 1, 2: 1, 3: 1},
        ),
        # Two leading, then two tied at the bottom.
        (
            [
                {"id": 1, "sort_key": (9, 2)},
                {"id": 2, "sort_key": (8, 1)},
                {"id": 3, "sort_key": (3, 0)},
                {"id": 4, "sort_key": (3, 0)},
            ],
            {1: 1, 2: 2, 3: 3, 4: 3},
        ),
        # Empty input.
        ([], {}),
    ],
)
def test_compute_player_ranks(players, expected):
    assert helpers.compute_player_ranks(players) == expected


def test_short_round():
    matches = database.Matches(MATCH_DATA, TEAMS)
    match = matches.getMatch("group_1-0")

    def short(round_name):
        match._round = round_name
        return match.short_round()

    # Known rounds use the lookup table.
    assert short("Group A") == "A"
    assert short("Final") == database.CUP
    assert short("Round of 32") == "1/16"
    # Group-stage rounds outside the table are shortened so the
    # date/time still fits on the /bet buttons.
    assert short("Group I") == "I"
    assert short("Group Stage - 1") == "GS1"
    assert short("League Stage - 2") == "LS2"
    # Unknown rounds pass through unchanged.
    assert short("Play-offs") == "Play-offs"


def score_players(match_result, player_pred, other_players_preds):
    all_players = [*other_players_preds, player_pred]
    return match_result.score(player_pred, all_players)


def test_group_score_fsnorm(monkeypatch):
    monkeypatch.setattr(database, "SCORE_MODE", "fsnorm")

    matches = database.Matches(MATCH_DATA, TEAMS)
    result_win = matches.getMatch("group_1-0").result()
    assert (
        score_players(result_win, database.Result(0, 0), [database.Result(0, 0)]) == 0
    )
    assert (
        score_players(result_win, database.Result(0, 1), [database.Result(0, 0)]) == 0
    )
    assert (
        score_players(result_win, database.Result(3, 0), [database.Result(0, 0)]) == 2.0
    )
    assert (
        score_players(result_win, database.Result(3, 0), [database.Result(0, 0), None])
        == 2.0
    )
    assert (
        score_players(result_win, database.Result(2, 0), [database.Result(0, 0)]) == 2.0
    )
    assert (
        score_players(result_win, database.Result(2, 1), [database.Result(0, 0)]) == 2.0
    )
    assert (
        score_players(result_win, database.Result(1, 0), [database.Result(0, 0)]) == 4.0
    )
    assert (
        score_players(result_win, database.Result(1, 0), [database.Result(0, 0), None])
        == 4.0
    )
    assert (
        score_players(result_win, database.Result(1, 0), [database.Result(1, 0)]) == 2.0
    )
    assert (
        score_players(
            result_win,
            database.Result(1, 0),
            [database.Result(1, 0), database.Result(1, 0)],
        )
        == 2.0
    )
    assert (
        score_players(
            result_win,
            database.Result(1, 0),
            [database.Result(1, 0), database.Result(2, 0)],
        )
        == 2.5
    )
    assert (
        score_players(
            result_win,
            database.Result(1, 0),
            [database.Result(1, 0), database.Result(0, 2)],
        )
        == 3.0
    )
    assert (
        score_players(
            result_win,
            database.Result(1, 0),
            [database.Result(0, 4), database.Result(0, 2)],
        )
        == 6.0
    )

    result_draw = matches.getMatch("group_1-1").result()
    assert (
        score_players(result_draw, database.Result(3, 0), [database.Result(1, 0)]) == 0
    )
    assert (
        score_players(result_draw, database.Result(0, 1), [database.Result(1, 0)]) == 0
    )
    assert (
        score_players(result_draw, database.Result(0, 0), [database.Result(1, 0)])
        == 2.0
    )
    assert (
        score_players(result_draw, database.Result(1, 1), [database.Result(1, 0)])
        == 4.0
    )
    assert (
        score_players(result_draw, database.Result(2, 2), [database.Result(1, 0)])
        == 2.0
    )
    assert (
        score_players(result_draw, database.Result(2, 2), [database.Result(1, 1)])
        == 1.0
    )
    assert (
        score_players(result_draw, database.Result(1, 1), [database.Result(1, 1)])
        == 2.0
    )


def test_playoff_score_fsnorm(monkeypatch):
    monkeypatch.setattr(database, "SCORE_MODE", "fsnorm")
    monkeypatch.setattr(database, "EXTRA_SCORE_MODE", "default")
    matches = database.Matches(MATCH_DATA, TEAMS)

    result_win = matches.getMatch("playoff_1-0").result()
    assert (
        score_players(result_win, database.Result(0, 0, 1), [database.Result(0, 1)])
        == 2.0
    )
    assert (
        score_players(result_win, database.Result(1, 1, 1), [database.Result(0, 1)])
        == 2.0
    )
    assert (
        score_players(result_win, database.Result(0, 0, 1), [database.Result(0, 1)])
        == 2.0
    )
    assert (
        score_players(result_win, database.Result(0, 0, 1), [database.Result(2, 1)])
        == 1.0
    )
    assert (
        score_players(result_win, database.Result(0, 0, 2), [database.Result(2, 1)])
        == 0.0
    )
    assert (
        score_players(result_win, database.Result(0, 1), [database.Result(2, 1)]) == 0.0
    )
    assert (
        score_players(result_win, database.Result(3, 0), [database.Result(0, 1)]) == 2.0
    )
    assert (
        score_players(result_win, database.Result(2, 1), [database.Result(0, 1)]) == 2.0
    )
    assert (
        score_players(result_win, database.Result(1, 0), [database.Result(0, 1)]) == 4.0
    )
    assert (
        score_players(result_win, database.Result(1, 0), [database.Result(2, 1)]) == 3.0
    )
    assert (
        score_players(result_win, database.Result(1, 0), [database.Result(1, 0)]) == 2.0
    )

    result_extra = matches.getMatch("playoff_1-1extra").result()
    assert (
        score_players(result_extra, database.Result(2, 1), [database.Result(3, 0)])
        == 3.0
    )
    assert (
        score_players(result_extra, database.Result(1, 0), [database.Result(3, 0)])
        == 1.0
    )
    assert (
        score_players(result_extra, database.Result(1, 0), [database.Result(2, 3)])
        == 2.0
    )
    assert (
        score_players(result_extra, database.Result(0, 1), [database.Result(2, 3)])
        == 0.0
    )
    assert (
        score_players(result_extra, database.Result(0, 0, 1), [database.Result(2, 3)])
        == 2.0
    )
    assert (
        score_players(result_extra, database.Result(0, 0, 2), [database.Result(2, 3)])
        == 0.0
    )
    assert (
        score_players(result_extra, database.Result(1, 1, 1), [database.Result(2, 3)])
        == 2.0
    )
    assert (
        score_players(result_extra, database.Result(1, 1, 2), [database.Result(2, 3)])
        == 0.0
    )

    result_penalty = matches.getMatch("playoff_1-1penalty").result()
    assert (
        score_players(result_penalty, database.Result(1, 0), [database.Result(2, 3)])
        == 2.0
    )
    assert (
        score_players(result_penalty, database.Result(2, 0), [database.Result(2, 3)])
        == 2.0
    )
    assert (
        score_players(result_penalty, database.Result(0, 2), [database.Result(2, 3)])
        == 0.0
    )
    assert (
        score_players(result_penalty, database.Result(0, 0, 1), [database.Result(2, 3)])
        == 2.0
    )
    assert (
        score_players(result_penalty, database.Result(0, 0, 2), [database.Result(2, 3)])
        == 0.0
    )
    assert (
        score_players(result_penalty, database.Result(1, 1, 1), [database.Result(2, 3)])
        == 4.0
    )
    assert (
        score_players(result_penalty, database.Result(1, 1, 2), [database.Result(2, 3)])
        == 2.0
    )


# ---------------------------------------------------------------------------
# Live match events ("goals feature")
#
# Covers the path: bot polls api-football -> sources.get_fixture_events ->
# helpers.send_match_event -> Telegram message. These exercise the formatting
# and the API error handling without touching the network.
# ---------------------------------------------------------------------------

EVENTS_GROUP_ID = -1001179590532
EVENTS_CONFIG = {"group_id": EVENTS_GROUP_ID}


class FakeTeam:
    def __init__(self, label="ARG"):
        self._label = label

    def label(self):
        return self._label


class FakeTeams:
    def __init__(self, label="ARG"):
        self._team = FakeTeam(label)
        self.requested = []

    def get_team(self, team_id):
        self.requested.append(team_id)
        return self._team


class FakeDb:
    def __init__(self, label="ARG"):
        self.teams = FakeTeams(label)


class FakeBot:
    def __init__(self):
        self.sent = []

    def send_message(self, group_id, text, **kwargs):
        self.sent.append((group_id, text))


def make_event(
    ev_type="Goal",
    detail="Normal Goal",
    elapsed=23,
    extra=None,
    player="Messi",
    team_id="Team1",
):
    """Shape mirrors api-football v3 fixtures/events entries."""
    return {
        "type": ev_type,
        "detail": detail,
        "team": {"id": team_id},
        "player": {"name": player},
        "time": {"elapsed": elapsed, "extra": extra},
    }


@pytest.mark.parametrize(
    "detail,expected",
    [
        ("Normal Goal", "⚽ 23': Messi - ARG"),
        ("Own Goal", "⚽(\U0001f926) 23': Messi - ARG"),
        ("Penalty", "⚽(1️⃣ 1️⃣) 23': Messi - ARG"),
        ("Missed Penalty", "\U0001f6ab⚽(1️⃣1️⃣)  23': Messi - ARG"),
    ],
)
def test_send_match_event_goal_variants(detail, expected):
    bot = FakeBot()
    helpers.send_match_event(
        bot, FakeDb("ARG"), EVENTS_CONFIG, None, make_event(detail=detail)
    )
    assert bot.sent == [(EVENTS_GROUP_ID, expected)]


def test_send_match_event_extra_time_formatting():
    bot = FakeBot()
    helpers.send_match_event(
        bot, FakeDb(), EVENTS_CONFIG, None, make_event(elapsed=90, extra=4)
    )
    assert bot.sent == [(EVENTS_GROUP_ID, "⚽ 90+4': Messi - ARG")]


def test_send_match_event_red_card():
    bot = FakeBot()
    helpers.send_match_event(
        bot,
        FakeDb(),
        EVENTS_CONFIG,
        None,
        make_event(ev_type="Card", detail="Red card", player="Ramos"),
    )
    assert bot.sent == [(EVENTS_GROUP_ID, "\U0001f7e5 23': Ramos - ARG")]


def test_send_match_event_var_includes_player():
    bot = FakeBot()
    helpers.send_match_event(
        bot,
        FakeDb(),
        EVENTS_CONFIG,
        None,
        make_event(ev_type="Var", detail="Goal cancelled", player="Messi"),
    )
    assert bot.sent == [
        (EVENTS_GROUP_ID, "\U0001f4fa 23': Goal cancelled - Messi - ARG")
    ]


def test_send_match_event_var_without_player():
    bot = FakeBot()
    event = make_event(ev_type="Var", detail="Penalty confirmed")
    event["player"] = {"id": None, "name": None}
    helpers.send_match_event(bot, FakeDb(), EVENTS_CONFIG, None, event)
    assert bot.sent == [(EVENTS_GROUP_ID, "\U0001f4fa 23': Penalty confirmed - ARG")]


def test_send_match_event_resolves_team_by_id():
    bot = FakeBot()
    db = FakeDb()
    helpers.send_match_event(
        bot, db, EVENTS_CONFIG, None, make_event(team_id="Team7")
    )
    assert db.teams.requested == ["Team7"]


@pytest.mark.parametrize(
    "event",
    [
        make_event(ev_type="Goal", detail="Goal Disallowed"),  # unknown goal detail
        make_event(ev_type="Card", detail="Yellow card"),  # only red cards notify
        make_event(ev_type="subst", detail="Substitution 1"),  # ignored type
    ],
)
def test_send_match_event_ignored_events_send_nothing(event):
    bot = FakeBot()
    helpers.send_match_event(bot, FakeDb(), EVENTS_CONFIG, None, event)
    assert bot.sent == []


def test_get_fixture_events_returns_api_response(monkeypatch):
    events = [make_event(), make_event(detail="Penalty")]
    monkeypatch.setattr(
        sources, "api_football", lambda config, resource, query: events
    )
    assert sources.get_fixture_events({}, 42) == events


def test_get_fixture_events_queries_correct_endpoint(monkeypatch):
    captured = {}

    def fake_api(config, resource, query):
        captured["resource"] = resource
        captured["query"] = query
        return []

    monkeypatch.setattr(sources, "api_football", fake_api)
    sources.get_fixture_events({}, 99)
    assert captured["resource"] == "fixtures/events"
    assert captured["query"] == {"fixture": 99}


def test_get_fixture_events_swallows_value_error(monkeypatch):
    def boom(config, resource, query):
        raise ValueError("RapidAPI error")

    monkeypatch.setattr(sources, "api_football", boom)
    # No events / quota / auth failure must degrade to an empty list, not raise.
    assert sources.get_fixture_events({}, 42) == []


class FakeResponse:
    def __init__(self, data):
        self._data = data

    def raise_for_status(self):
        pass

    def json(self):
        return self._data


def test_api_football_returns_response_on_results(monkeypatch):
    payload = {"results": 2, "response": [{"a": 1}, {"b": 2}]}
    monkeypatch.setattr(
        sources.requests,
        "get",
        lambda url, headers=None, params=None: FakeResponse(payload),
    )
    out = sources.api_football(
        {"api_token": "x"}, "fixtures/events", {"fixture": 1}
    )
    assert out == [{"a": 1}, {"b": 2}]


def test_api_football_raises_on_zero_results(monkeypatch):
    payload = {"results": 0, "errors": {"token": "invalid"}, "response": []}
    monkeypatch.setattr(
        sources.requests,
        "get",
        lambda url, headers=None, params=None: FakeResponse(payload),
    )
    with pytest.raises(ValueError):
        sources.api_football({"api_token": "x"}, "fixtures/events", {"fixture": 1})


# ---------------------------------------------------------------------------
# Shared event storage (single updater writes JSON; both bots read it)
# ---------------------------------------------------------------------------

# Fixed "now" for event-window tests; window is 3h after kickoff.
FIXED_NOW = pytz.utc.localize(datetime.datetime(2026, 6, 11, 18, 0))


def _events_config(tmp_path):
    return {"data_dir": str(tmp_path), "league_id": 1, "season": 2026}


def _raw_fixture(fid, status="NS", date="2026-06-11T17:00:00+00:00"):
    return {"fixture": {"id": fid, "status": {"short": status}, "date": date}}


def _write_raw_fixtures(tmp_path, fixtures):
    with open(tmp_path / "fixtures-1-2026.json", "w") as fp:
        json.dump(fixtures, fp)


def test_load_events_missing_returns_empty(tmp_path):
    config = _events_config(tmp_path)
    assert sources.load_events(config) == {}
    assert sources.get_stored_events(config, 99) == []


def test_get_stored_events_accepts_int_and_str_ids(tmp_path):
    config = _events_config(tmp_path)
    with open(tmp_path / "events-1-2026.json", "w") as fp:
        json.dump({"10": [{"type": "Goal"}]}, fp)
    assert sources.get_stored_events(config, 10) == [{"type": "Goal"}]
    assert sources.get_stored_events(config, "10") == [{"type": "Goal"}]
    assert sources.get_stored_events(config, 11) == []


def test_save_events_fetches_only_matches_in_window(tmp_path, monkeypatch):
    config = _events_config(tmp_path)
    monkeypatch.setattr(sources.utils, "utcnow", lambda: FIXED_NOW)
    # now = 18:00; window = kickoff .. kickoff+3h
    _write_raw_fixtures(
        tmp_path,
        [
            _raw_fixture(10, "NS", "2026-06-11T17:00:00+00:00"),  # 1h in -> fetch
            _raw_fixture(20, "NS", "2026-06-11T20:00:00+00:00"),  # future -> skip
            _raw_fixture(30, "NS", "2026-06-11T14:00:00+00:00"),  # window ended -> skip
            _raw_fixture(40, "FT", "2026-06-11T17:00:00+00:00"),  # finished -> skip
        ],
    )
    calls = []

    def fake_events(cfg, fid):
        calls.append(fid)
        return [make_event(player="P%s" % fid)]

    monkeypatch.setattr(sources, "get_fixture_events", fake_events)
    sources.save_events(config)

    # No fixtures API call happened — only one events call, for the in-window match.
    assert calls == [10]
    assert set(sources.load_events(config).keys()) == {"10"}
    assert sources.get_stored_events(config, 10) == [make_event(player="P10")]


def test_save_events_keeps_last_snapshot_after_match_finishes(tmp_path, monkeypatch):
    config = _events_config(tmp_path)
    monkeypatch.setattr(sources.utils, "utcnow", lambda: FIXED_NOW)
    # fixture 30's last snapshot, stored on a previous run
    with open(tmp_path / "events-1-2026.json", "w") as fp:
        json.dump({"30": [{"old": True}]}, fp)
    _write_raw_fixtures(
        tmp_path,
        [
            _raw_fixture(30, "FT", "2026-06-11T17:00:00+00:00"),  # finished -> skip
            _raw_fixture(10, "NS", "2026-06-11T17:30:00+00:00"),  # in window -> fetch
        ],
    )
    calls = []

    def fake_events(cfg, fid):
        calls.append(fid)
        return [make_event(player="P%s" % fid)]

    monkeypatch.setattr(sources, "get_fixture_events", fake_events)
    sources.save_events(config)

    # finished (30) not refetched but its snapshot is preserved; live (10) refetched
    assert calls == [10]
    stored = sources.load_events(config)
    assert stored["30"] == [{"old": True}]
    assert stored["10"] == [make_event(player="P10")]


def test_save_events_atomic_write_leaves_no_temp_files(tmp_path, monkeypatch):
    config = _events_config(tmp_path)
    monkeypatch.setattr(sources.utils, "utcnow", lambda: FIXED_NOW)
    _write_raw_fixtures(tmp_path, [_raw_fixture(10, "NS", "2026-06-11T17:00:00+00:00")])
    monkeypatch.setattr(sources, "get_fixture_events", lambda cfg, fid: [])
    sources.save_events(config)
    names = [p.name for p in tmp_path.iterdir()]
    assert "events-1-2026.json" in names
    assert not [n for n in names if n.endswith(".tmp")]


def test_get_data_file_uses_shared_dir_when_set():
    config = {
        "data_dir": "/inst",
        "shared_dir": "/shared",
        "league_id": 1,
        "season": 2026,
    }
    assert conf.get_data_file(config, "events") == "/shared/events-1-2026.json"
    assert conf.get_data_file(config, "fixtures") == "/shared/fixtures-1-2026.json"


def test_get_data_file_falls_back_to_data_dir():
    config = {"data_dir": "/inst", "league_id": 1, "season": 2026}
    assert conf.get_data_file(config, "events") == "/inst/events-1-2026.json"


def _updater_config(tmp_path, intervals):
    return {
        "data_dir": str(tmp_path),
        "league_id": 1,
        "season": 2026,
        "update_intervals": intervals,
    }


def _patch_updaters(monkeypatch):
    from betbot import commands

    calls = []
    monkeypatch.setattr(commands.utils, "utcnow", lambda: FIXED_NOW)
    monkeypatch.setitem(
        commands._RESOURCE_UPDATERS, "fixtures", lambda c: calls.append("fixtures")
    )
    monkeypatch.setitem(
        commands._RESOURCE_UPDATERS, "events", lambda c: calls.append("events")
    )
    return commands, calls


def test_update_all_runs_due_resources_and_records_state(tmp_path, monkeypatch):
    commands, calls = _patch_updaters(monkeypatch)
    cfg = _updater_config(tmp_path, {"fixtures": 15, "events": 3})
    commands.update_all(cfg)
    assert calls == ["fixtures", "events"]
    state = sources.load_update_state(cfg)
    assert set(state.keys()) == {"fixtures", "events"}


def test_update_all_throttles_each_resource_by_interval(tmp_path, monkeypatch):
    commands, calls = _patch_updaters(monkeypatch)
    cfg = _updater_config(tmp_path, {"fixtures": 15, "events": 3})
    five_min_ago = (FIXED_NOW - datetime.timedelta(minutes=5)).isoformat()
    sources.save_update_state(cfg, {"fixtures": five_min_ago, "events": five_min_ago})
    commands.update_all(cfg)
    # after 5 min: events (every 3) is due, fixtures (every 15) is not
    assert calls == ["events"]


def test_update_all_skips_unconfigured_resources(tmp_path, monkeypatch):
    commands, calls = _patch_updaters(monkeypatch)
    cfg = _updater_config(tmp_path, {"events": 3})
    commands.update_all(cfg)
    assert calls == ["events"]


def test_send_match_event_group_id_override():
    # The /testEvents preview posts to the invoking chat, not the configured group.
    bot = FakeBot()
    helpers.send_match_event(
        bot, FakeDb(), EVENTS_CONFIG, None, make_event(), group_id=999
    )
    assert bot.sent == [(999, "⚽ 23': Messi - ARG")]


def test_sample_match_events_all_render():
    bot = FakeBot()
    db = FakeDb("ARG")
    events = helpers.sample_match_events(team_id="T1")
    for event in events:
        helpers.send_match_event(bot, db, EVENTS_CONFIG, None, event, group_id=1)
    # Preview set contains only rendered types, so every sample produces a message.
    assert len(bot.sent) == len(events)
    texts = [t for _, t in bot.sent]
    assert texts[0] == "⚽ 12': Messi - ARG"
    assert any(t.startswith("📺") for t in texts)  # VAR
    assert any(t.startswith("🟥") for t in texts)  # red card
    # All events resolve the given team through db.teams.
    assert db.teams.requested == ["T1"] * len(events)


def test_set_fixture_events_round_trips_through_shared_file(tmp_path):
    config = {"data_dir": str(tmp_path), "league_id": 1, "season": 2026}
    # pre-existing events for another fixture must be preserved (merge, not clobber)
    with open(tmp_path / "events-1-2026.json", "w") as fp:
        json.dump({"50": [{"type": "Goal"}]}, fp)
    events = helpers.sample_match_events(team_id="T1")
    sources.set_fixture_events(config, 100, events)
    assert sources.get_stored_events(config, 100) == events
    assert sources.get_stored_events(config, 50) == [{"type": "Goal"}]
