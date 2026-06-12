from collections import namedtuple

from betbot import database, helpers, messages

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
    assert short("Group Stage - 1") == "1"
    assert short("League Stage - 2") == "2"
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
