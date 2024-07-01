from betbot import database

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
