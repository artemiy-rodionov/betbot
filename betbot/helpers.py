import logging
import math
from collections import defaultdict

import telebot

from .messages import *
from . import messages, utils

logger = logging.getLogger(__name__)
MATCHES_PER_PAGE = 8


def check_forwarded_from(bot, message):
    if message.reply_to_message is None:
        bot.send_message(message.chat.id, messages.REGISTER_SHOULD_BE_REPLY)
        return None
    if message.reply_to_message.forward_from is None:
        bot.send_message(message.chat.id, messages.REGISTER_SHOULD_BE_REPLY_TO_FORWARD)
        return None
    return message.reply_to_message.forward_from


def change_queen(bot, db_helper, message, is_queen):
    forward_from = check_forwarded_from(bot, message)
    if forward_from is None:
        return
    if not db_helper.is_registered(forward_from):
        bot.send_message(message.chat.id, messages.USER_NOT_REGISTERED)
        return
    db_helper.get_db().players.changeIsQueen(forward_from.id, is_queen)
    bot.send_message(message.chat.id, messages.SUCCESS)


def create_match_button(match, tz, prediction=None):
    start_time_str = match.start_time().astimezone(tz).strftime("%d.%m %H:%M")
    label = "{}: {} {}".format(
        match.short_round(), match.label(prediction, short=True), start_time_str
    )
    return telebot.types.InlineKeyboardButton(
        label, callback_data="b_{}".format(match.id())
    )


def send_scores(bot, db, config, reply_message=None, finished_matches=None, is_playoff=False):
    logger.info('Send scores for matches %s, playoff: %s', finished_matches, is_playoff)
    extra_msg = ""
    finished_matches_ids = set()
    if finished_matches is not None:
        extra_msg = "Результаты матчей:\n"
        for m in finished_matches:
            if is_playoff and not m.is_playoff():
                continue
            extra_msg += f"{m.label(m.result(), True)}\n"
            finished_matches_ids.add(int(m.id()))
    unow = utils.utcnow()
    results = db.predictions.genResults(unow, is_playoff=is_playoff)

    text = f"{extra_msg}\n"
    if is_playoff:
        text += f"Таблица Плей-офф: \n"
    else:
        text += f"Таблица: \n"
    text += "\n```\n"
    for idx, player in enumerate(results["players"].values()):
        is_queen = " ♛ " if player["is_queen"] else " "
        text += f'{idx+1}. {player["name"]}{is_queen}- {player["score"]}'
        if finished_matches:
            matches_score = sum(
                0 if pr["score"] is None else pr["score"]
                for pr in player["predictions"]
                if int(pr["match_id"]) in finished_matches_ids
            )
            SCORE_MODE = config["score_mode"]
            if SCORE_MODE == "fsnorm":
                matches_score = round(matches_score, 2)
                text += f" (+{matches_score:.2f})"
            else:
                text += f" (+{matches_score})"
        text += "\n"
    text += "\n```\n"
    group_id = config["group_id"]
    if reply_message is not None:
        group_id = reply_message.chat.id
    keyboard = telebot.types.InlineKeyboardMarkup(row_width=1)
    keyboard.add(
        telebot.types.InlineKeyboardButton(
            messages.CHECK_RESULTS_BUTTON, url=config["results_url"]
        )
    )
    bot.send_message(
        group_id,
        text,
        reply_to_message_id=reply_message.message_id if reply_message else None,
        parse_mode="Markdown",
        reply_markup=keyboard,
    )


def send_match_event(bot, db, config, match, event):
    ev_type = event["type"]
    detail = event["detail"]
    team = db.teams.get_team(event["team"]["id"])
    time = f"{event['time']['elapsed']}"
    if event['time']['extra'] is not None:
        time += f"+{event['time']['extra']}"
    time += "'"
    if ev_type == "Goal":
        if detail == "Normal Goal":
            prefix = "⚽"
        elif detail == "Own Goal":
            prefix = "⚽(🤦)"
        elif detail == "Penalty":
            prefix = "⚽(1️⃣ 1️⃣)"
        elif detail == "Missed Penalty":
            prefix = "🚫⚽(1️⃣1️⃣) "
        else:
            return
        text = f"{prefix} {time}: {event['player']['name']} - {team.label()}"

    elif ev_type == "Var":
        text = f"📺 {time}: {event['detail']} - {team.label()}"
    elif ev_type == "Card" and detail == "Red card":
        text = (
            f"🟥 {time}: {event['player']['name']} - {team.label()}"
        )
    else:
        return

    group_id = config["group_id"]
    bot.send_message(
        group_id,
        text,
    )


def send_standings(bot, db, config, reply_message=None):
    text = "\nТаблица Чемпионата: \n"
    if not db.standings:
        text += "Таблица пока не загружена"

    else:
        text += "\n```\n"
        standings = db.standings.get_standings()
        for team in standings:
            text += f'{team["rank"]}. {team["team"]["name"]} - {team["points"]} ({team["form"]})'
            text += "\n"
        text += "\n```\n"
        text += f'Последнее обновление: {standings[0]["update"]}'
    group_id = config["group_id"]
    if reply_message is not None:
        group_id = reply_message.chat.id
    bot.send_message(
        group_id,
        text,
        reply_to_message_id=reply_message.message_id if reply_message else None,
        parse_mode="Markdown",
    )


def send_match_predictions(bot, db, config, match):
    keyboard = telebot.types.InlineKeyboardMarkup(row_width=1)
    keyboard.add(
        telebot.types.InlineKeyboardButton(
            messages.CHECK_RESULTS_BUTTON, url=config["results_url"]
        )
    )
    SCORE_MODE = config["score_mode"]
    player_match_predictions = db.predictions.getForMatch(match)
    text = messages.RESULTS_TITLE % match.label()
    text += "\n```\n"
    match_predictions = [mp[1] for mp in player_match_predictions]
    for player, pred in player_match_predictions:
        pred_score_text = ""
        if SCORE_MODE == "fsnorm":
            pred_winner_score = (
                pred.fsnorm_winner_score(pred, match_predictions) if pred else None
            )
            pred_exact_score = (
                pred.fsnorm_exact_score(pred, match_predictions) if pred else None
            )
            pred_score_text = (
                f"({pred_exact_score:.2f}, {pred_winner_score:.2f})"
                if pred is not None
                else "(0)"
            )
        pred_text = pred.label() if pred else "-"
        is_queen = " ♛ " if player.is_queen() else " "
        text += f"{player.name()}{is_queen}: {pred_text} {pred_score_text}\n"
    text += "\n```\n"
    bot.send_message(
        config["group_id"], text, parse_mode="Markdown", reply_markup=keyboard
    )


def create_matches_page(db, page_idx, player, matches_per_page=MATCHES_PER_PAGE):
    matches = db.matches.getMatchesAfter(utils.utcnow(), days_limit=60)
    matches_number = len(matches)
    if matches_number == 0:
        return None

    pages_number = max(1, math.ceil(matches_number / matches_per_page))
    page_idx = min(page_idx, pages_number - 1)
    first_match_ix = page_idx * matches_per_page
    last_match_ix = (page_idx + 1) * matches_per_page
    logger.debug(
        f"Matches: {len(matches)};indexes for page: {first_match_ix}:{last_match_ix}"
        f"Pages: {pages_number}; Current page: {page_idx+1}"
    )
    matches = matches[first_match_ix:last_match_ix]
    keyboard = telebot.types.InlineKeyboardMarkup(row_width=1)
    predictions = defaultdict(lambda: None)
    for m, r in db.predictions.getForPlayer(player):
        predictions[m.id()] = r
    for m in matches:
        keyboard.add(create_match_button(m, player.tz(), predictions[m.id()]))
    navs = []
    if pages_number > 1:
        navs.append(
            telebot.types.InlineKeyboardButton(
                messages.LEFT_ARROW,
                callback_data="l_%d" % ((page_idx + pages_number - 1) % pages_number),
            )
        )
        navs.append(
            telebot.types.InlineKeyboardButton(
                "%d/%d" % (page_idx + 1, pages_number), callback_data="l_%d" % page_idx
            )
        )
        navs.append(
            telebot.types.InlineKeyboardButton(
                messages.RIGHT_ARROW,
                callback_data="l_%d" % ((page_idx + 1) % pages_number),
            )
        )
        keyboard.row(*navs)
    title = messages.CHOOSE_MATCH_TITLE
    return (title, keyboard)


def send_markdown(bot, message, text, **kwargs):
    logger.info(text)
    bot.send_message(message.chat.id, text, parse_mode="Markdown", **kwargs)
