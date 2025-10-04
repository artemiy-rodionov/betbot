#!/usr/bin/env python
"""
Created on Sat Jun 04 12:05:50 2016

@author: SSundukov
"""

from collections import defaultdict
from functools import cached_property
import os.path
import json
import logging
import re
import datetime
import time
import traceback
import threading

import pytz
import tabulate
from betbot import sources
import schedule
import telebot

from config import config
from . import conf, helpers, database, messages, utils, commands

telebot.logger.setLevel(logging.DEBUG)
logger = logging.getLogger(__name__)

UPDATE_INTERVAL_SEC = 60
REMIND_BEFORE = datetime.timedelta(minutes=30)
REMIND_DAY_BEFORE = datetime.timedelta(hours=24)

RESULTS_URL = config["results_url"]
EXTRA_SCORE_MODE = config["extra_score_mode"]
EVENTS_ENABLED = config.get("events_enabled", False)
PLAYOFF_TABLE_ENABLED = config.get("playoff_table_enabled", False)

# Special bot IDs - using very large negative numbers to avoid Telegram ID conflicts
# Telegram user IDs are positive integers, so negative numbers are safe
BOT_ID_ONE_ZERO = -999999999  # The 1-0 betting bot

bot = telebot.TeleBot(config["token"])


class DbHelper:
    def __init__(self):
        self._config = config
        self.db_lock = threading.Lock()

    @cached_property
    def db(self):
        return database.Database(config)

    def get_db(self):
        with self.db_lock:
            return self.db

    def reload_db(self):
        with self.db_lock:
            self.db.reload_data()

    def register_player(self, user):
        assert not self.is_registered(user)
        logger.info(f"Register player {user}")
        return self.get_db().players.createPlayer(
            user.id, user.first_name, user.last_name, is_bot=False
        )

    def register_bot_player(self, bot_id, bot_name):
        """Register a bot player that will automatically make 1-0 bets"""
        assert not self.is_registered_by_id(bot_id)
        logger.info(f"Register bot player {bot_name} with id {bot_id}")
        return self.get_db().players.createPlayer(
            bot_id, bot_name, "Bot", is_queen=False, is_bot=True
        )

    def is_registered_by_id(self, user_id):
        """Check if a user is registered by ID"""
        return self.get_db().players.isRegistered(user_id)

    def get_player(self, user):
        assert self.is_registered(user)
        return self.get_db().players.getPlayer(user.id)

    def is_registered(self, user):
        return self.get_db().players.isRegistered(user.id)

    def is_admin(self, user):
        return self.get_db().players.isAdmin(user.id)


def make_automatic_bot_bets():
    """Make automatic 1-0 bets for all bot players on all matches"""
    try:
        db = db_helper.get_db()
        bot_players = db.players.getBotPlayers()

        if not bot_players:
            return

        unow = utils.utcnow()
        # Get ALL matches (both past and future)
        all_matches = list(db.matches.matches.values())

        bets_made = 0
        for bot_player in bot_players:
            # Get existing predictions once per bot player for efficiency
            existing_predictions = db.predictions.getForPlayer(bot_player)
            existing_match_ids = {m.id() for m, r in existing_predictions}

            for match in all_matches:
                if match.id() not in existing_match_ids:
                    # Create 1-0 result (team 1 wins 1-0)
                    result = database.Result(1, 0)

                    # Add the prediction
                    db.predictions.addPrediction(bot_player, match, result, unow)
                    bets_made += 1
                    logger.info(
                        f"Bot player {bot_player.name()} (ID: {bot_player.id()}) "
                        f"made automatic 1-0 bet on match {match.id()}: {match.label(result)}"
                    )

        if bets_made > 0:
            logger.info(
                f"Made {bets_made} automatic 1-0 bets for {len(bot_players)} bot players on all matches"
            )

    except Exception as e:
        logger.error(f"Error making automatic bot bets: {e}")


db_helper = DbHelper()


@bot.message_handler(commands=["help"])
def help_command(message):
    text = messages.HELP_MSG % RESULTS_URL
    if db_helper.is_admin(message.from_user):
        text += "\n" + messages.ADMIN_HELP_MSG
    helpers.send_markdown(bot, message, text)


@bot.message_handler(commands=["timezone"], func=lambda m: m.chat.type == "private")
def set_tz_command(message):
    player = db_helper.get_player(message.from_user)
    if not player:
        return
    msg = message.text
    cand_tz = msg.replace("/timezone", "").strip()
    error_msg = ""
    if cand_tz:
        try:
            tz = pytz.timezone(cand_tz)
        except pytz.UnknownTimeZoneError:
            error_msg = f"\nОшибка: Неизвестный часовой пояс {cand_tz}"
        else:
            pid = player.id()
            db_helper.get_db().players.changeTz(pid, tz.zone)
            player = db_helper.get_player(message.from_user)
    zone = player.tz().zone
    text = messages.TIMEZONE_MSG.format(tz=zone.replace("_", " "))
    text += "\n\n" + messages.TIMEZONE_HELP_MSG + error_msg
    logging.debug("Timezone text", text)
    helpers.send_markdown(bot, message, text)


@bot.message_handler(commands=["scores"])
def scores(message):
    helpers.send_scores(bot, db_helper.get_db(), config, reply_message=message)


@bot.message_handler(commands=["playoffScores"])
def playoff_scores(message):
    helpers.send_scores(
        bot, db_helper.get_db(), config, reply_message=message, is_playoff=True
    )


@bot.message_handler(commands=["standings"])
def standings(message):
    helpers.send_standings(bot, db_helper.get_db(), config, reply_message=message)


@bot.message_handler(
    commands=["sendLast"], func=lambda m: db_helper.is_admin(m.from_user)
)
def send_last(message):
    for m in db_helper.get_db().matches.getMatchesBefore(utils.utcnow()):
        if m.is_finished():
            continue
        helpers.send_match_predictions(bot, db_helper.get_db(), config, m)


@bot.message_handler(
    commands=["finalScores"], func=lambda m: db_helper.is_admin(m.from_user)
)
def send_final_scores(message):
    reply_message = message
    unow = utils.utcnow()
    results = db_helper.get_db().predictions.genResults(unow, verbose=True)
    headers = [
        "Место",
        "Имя",
        "Очки",
        "Точный счет",
        "Разница",
        "Победитель",
        "Пенальти",
    ]
    stats = []
    for idx, player in enumerate(results["players"].values()):
        is_queen = " ♛ " if player["is_queen"] else " "
        stats.append(
            [
                idx + 1,
                player["name"] + is_queen,
                player["score"],
                len([p for p in player["predictions"] if p["is_exact_score"]]),
                len(
                    [
                        p
                        for p in player["predictions"]
                        if p.get("is_difference_score", False)
                    ]
                ),
                len(
                    [
                        p
                        for p in player["predictions"]
                        if p.get("is_winner_score", False)
                    ]
                ),
                len(
                    [
                        p
                        for p in player["predictions"]
                        if p.get("is_penalty_score", False)
                    ]
                ),
            ]
        )
    text = "\nФинальная Таблица: \n"
    text += "\n```\n"
    text += tabulate.tabulate(stats, headers, tablefmt="pretty")
    text += "\n```\n"

    group_id = message.chat.id
    keyboard = telebot.types.InlineKeyboardMarkup(row_width=1)
    keyboard.add(
        telebot.types.InlineKeyboardButton(
            messages.CHECK_RESULTS_BUTTON, url=RESULTS_URL
        )
    )
    bot.send_message(
        group_id,
        text,
        reply_to_message_id=reply_message.message_id if reply_message else None,
        parse_mode="Markdown",
        reply_markup=keyboard,
    )


@bot.message_handler(
    commands=["chartRace"], func=lambda m: db_helper.is_admin(m.from_user)
)
def send_chart_race(message):
    fpath = conf.get_chart_race_file(config)
    if not os.path.exists(fpath):
        return bot.send_message(message.chat.id, messages.FAILURE)
    with open(fpath, "rb") as fp:
        video_data = fp.read()
    group_id = message.chat.id
    bot.send_video(group_id, video_data)


@bot.message_handler(commands=["bet"], func=lambda m: m.chat.type != "private")
def bet_cmd_public_err(message):
    cfg = config
    msg = f"{messages.SEND_PRIVATE_MSG} {cfg['bot_name']}"
    bot.send_message(message.chat.id, msg, reply_to_message_id=message.message_id)


@bot.message_handler(func=lambda m: m.chat.type != "private")
def on_not_private(message):
    pass
    # bot.send_message(
    #     message.chat.id, SEND_PRIVATE_MSG, reply_to_message_id=message.message_id
    # )


@bot.message_handler(
    commands=["registerAdmin"], func=lambda m: db_helper.is_admin(m.from_user)
)
def register_admin(message):
    user = message.from_user
    if db_helper.is_registered(user):
        player = db_helper.get_player(user)
        bot.send_message(
            message.chat.id, messages.ALREADY_REGISTERED % (player.name(), player.id())
        )
        return
    player = db_helper.register_player(user)
    bot.send_message(
        message.chat.id,
        messages.REGISTRATION_SUCCESS
        % (player.name(), player.short_name(), player.id()),
    )
    bot.send_message(
        player.id(),
        messages.START_MSG % player.short_name() + messages.HELP_MSG % RESULTS_URL,
        parse_mode="Markdown",
    )


@bot.message_handler(
    commands=["register"], func=lambda m: db_helper.is_admin(m.from_user)
)
def register(message):
    forward_from = helpers.check_forwarded_from(bot, message)
    if forward_from is None:
        return
    if db_helper.is_registered(forward_from):
        player = db_helper.get_player(forward_from)
        bot.send_message(
            message.chat.id, messages.ALREADY_REGISTERED % (player.name(), player.id())
        )
        return
    player = db_helper.register_player(message.reply_to_message.forward_from)
    bot.send_message(
        message.chat.id,
        messages.REGISTRATION_SUCCESS
        % (player.name(), player.short_name(), player.id()),
    )
    bot.send_message(
        player.id(),
        messages.START_MSG % player.short_name() + messages.HELP_MSG % RESULTS_URL,
        parse_mode="Markdown",
    )


@bot.message_handler(
    commands=["makeQueen"], func=lambda m: db_helper.is_admin(m.from_user)
)
def make_queen(message):
    helpers.change_queen(bot, db_helper, message, True)


@bot.message_handler(
    commands=["unmakeQueen"], func=lambda m: db_helper.is_admin(m.from_user)
)
def unmake_queen(message):
    helpers.change_queen(bot, db_helper, message, False)


@bot.message_handler(
    commands=["registerBot"], func=lambda m: db_helper.is_admin(m.from_user)
)
def register_bot(message):
    """Register the 1-0 betting bot (only one allowed)"""
    # Check if 1-0 bot already exists
    if db_helper.is_registered_by_id(BOT_ID_ONE_ZERO):
        existing_bot = db_helper.get_db().players.getPlayer(BOT_ID_ONE_ZERO)
        bot.send_message(
            message.chat.id,
            f"❌ 1-0 betting bot already exists: '{existing_bot.name()}' (ID: {existing_bot.id()})\n"
            f"Use /listBots to see existing bots.",
        )
        return

    # Parse the command to get bot name (optional)
    msg_parts = message.text.split(maxsplit=1)
    bot_name = msg_parts[1].strip() if len(msg_parts) > 1 else "OneZero"
    
    if not bot_name:
        bot_name = "OneZero"

    try:
        bot_player = db_helper.register_bot_player(BOT_ID_ONE_ZERO, bot_name)
        bot.send_message(
            message.chat.id,
            f"✅ 1-0 betting bot '{bot_player.name()}' (ID: {bot_player.id()}) registered successfully!\n"
            f"This bot will automatically make 1-0 predictions on ALL matches.\n"
            f"Only one 1-0 bot is allowed in the system.",
        )
        logger.info(f"1-0 bot player {bot_name} registered with ID {BOT_ID_ONE_ZERO}")
    except Exception as e:
        bot.send_message(
            message.chat.id, f"❌ Failed to register 1-0 bot player: {str(e)}"
        )
        logger.error(f"Failed to register 1-0 bot player {bot_name}: {e}")


@bot.message_handler(
    commands=["listBots"], func=lambda m: db_helper.is_admin(m.from_user)
)
def list_bots(message):
    """List all registered bot players"""
    try:
        db = db_helper.get_db()
        bot_players = db.players.getBotPlayers()

        if not bot_players:
            bot.send_message(message.chat.id, "❌ No bot players registered")
            return

        lines = ["🤖 **Registered Bot Players:**"]
        for bot_player in bot_players:
            lines.append(f"• {bot_player.name()} (ID: {bot_player.id()})")

        bot.send_message(message.chat.id, "\n".join(lines), parse_mode="Markdown")

    except Exception as e:
        bot.send_message(message.chat.id, f"❌ Error listing bot players: {str(e)}")
        logger.error(f"Error listing bot players: {e}")


@bot.message_handler(
    commands=["removeBot"], func=lambda m: db_helper.is_admin(m.from_user)
)
def remove_bot(message):
    """Remove the 1-0 betting bot"""
    try:
        if not db_helper.is_registered_by_id(BOT_ID_ONE_ZERO):
            bot.send_message(message.chat.id, "❌ No 1-0 betting bot is registered")
            return

        # Get bot info before removal
        existing_bot = db_helper.get_db().players.getPlayer(BOT_ID_ONE_ZERO)
        bot_name = existing_bot.name()

        # Remove bot from database
        with db_helper.get_db().players.db() as db:
            db.execute("DELETE FROM players WHERE id=?", (BOT_ID_ONE_ZERO,))
            # Also remove all predictions made by this bot
            db.execute("DELETE FROM predictions WHERE player_id=?", (BOT_ID_ONE_ZERO,))

        bot.send_message(
            message.chat.id,
            f"✅ 1-0 betting bot '{bot_name}' (ID: {BOT_ID_ONE_ZERO}) removed successfully!\n"
            f"All predictions made by this bot have also been deleted.",
        )
        logger.info(f"1-0 bot player {bot_name} removed with ID {BOT_ID_ONE_ZERO}")

    except Exception as e:
        bot.send_message(message.chat.id, f"❌ Error removing bot player: {str(e)}")
        logger.error(f"Error removing bot player: {e}")


@bot.message_handler(
    commands=["updateFixtures"], func=lambda m: db_helper.is_admin(m.from_user)
)
def cmd_update_fixtures(message):
    commands.update_fixtures()
    UpdateJob.init_update_job()
    bot.send_message(message.chat.id, "Success")


@bot.message_handler(
    commands=["updateStandings"], func=lambda m: db_helper.is_admin(m.from_user)
)
def cmd_update_standings(message):
    commands.update_standings()
    db_helper.get_db().reload_standings()
    bot.send_message(message.chat.id, "Success")


@bot.message_handler(func=lambda m: not db_helper.is_registered(m.from_user))
def on_not_registered(message):
    msg = messages.NOT_REGISTERED.format(admin_name=config["admin_name"])
    bot.send_message(message.chat.id, msg)


@bot.message_handler(commands=["bet"])
def start_betting(message):
    db_helper.reload_db()
    player = db_helper.get_player(message.from_user)
    page_to_send = helpers.create_matches_page(db_helper.get_db(), 0, player)
    if page_to_send is None:
        bot.send_message(message.chat.id, messages.NO_MATCHES_MSG)
        return
    title, keyboard = page_to_send
    bot.send_message(message.chat.id, title, reply_markup=keyboard)


@bot.message_handler(commands=["mybets"])
def list_my_bets(message):
    player = db_helper.get_player(message.from_user)
    predictions = db_helper.get_db().predictions.getForPlayer(player)

    if len(predictions) == 0:
        bot.send_message(message.chat.id, messages.NO_BETS_MSG)
        return

    lines = []
    for m, r in predictions:
        lines.append("%s: %s" % (m.short_round(), m.label(r, short=True)))
    lines.append(messages.PRESS_BET + " " + messages.RESULTS_TABLE % RESULTS_URL)
    bot.send_message(message.chat.id, "\n".join(lines), parse_mode="Markdown")


# keep last
@bot.message_handler(func=lambda m: True)
def help(message):
    bot.send_message(
        message.chat.id, messages.HELP_MSG % RESULTS_URL, parse_mode="Markdown"
    )


# l_<page>
# b_<match_id>
# b_<match_id>_<goals1>
# b_<match_id>_<goals1>_<goals2>
# b_<match_id>_<goals1>_<goals2>_<winner>
@bot.callback_query_handler(lambda m: True)
def handle_query(query):
    if query.message is None:
        bot.answer_callback_query(
            callback_query_id=query.id,
            text=messages.ERROR_MESSAGE_ABSENT,
            show_alert=True,
        )
        return
    bot.answer_callback_query(callback_query_id=query.id)
    player = db_helper.get_player(query.from_user)
    data = query.data or ""

    db = db_helper.get_db()

    def edit_message(text, **kwargs):
        bot.edit_message_text(
            text,
            chat_id=query.message.chat.id,
            message_id=query.message.message_id,
            parse_mode="Markdown",
            **kwargs,
        )

    def on_error(line_no):
        edit_message(messages.NAVIGATION_ERROR % (line_no, RESULTS_URL))

    m = (
        re.match(r"^b_([^_]*)$", data)
        or re.match(r"^b_([^_]*)_([0-9])$", data)
        or re.match(r"^b_([^_]*)_([0-9])_([0-9])$", data)
        or re.match(r"^b_([^_]*)_([0-9])_([0-9])_([12])$", data)
    )

    if m is None:
        m = re.match(r"^l_([0-9]+)$", data)
        if m is None:
            return on_error(utils.lineno())
        page = int(m.group(1))
        page_to_send = helpers.create_matches_page(db_helper.get_db(), page, player)
        if page_to_send is None:
            return edit_message(messages.NO_MATCHES_MSG)
        title, keyboard = page_to_send
        return edit_message(title, reply_markup=keyboard)

    match = db.matches.getMatch(int(m.group(1)))
    if match is None:
        return on_error(utils.lineno())

    args_len = len(m.groups())
    if args_len in [1, 2]:

        def make_button(score):
            cb_data = data + "_%d" % score
            return telebot.types.InlineKeyboardButton(str(score), callback_data=cb_data)

        keyboard = telebot.types.InlineKeyboardMarkup(row_width=3)
        keyboard.row(make_button(0)).row(
            make_button(1), make_button(2), make_button(3)
        ).row(make_button(4), make_button(5), make_button(6)).row(
            make_button(7), make_button(8), make_button(9)
        )
        team = match.team(0) if args_len == 1 else match.team(1)
        return edit_message(
            messages.SCORE_REQUEST % (team.flag(), team.name()), reply_markup=keyboard
        )

    if args_len == 4:
        if not match.is_playoff():
            return on_error(utils.lineno())
        if m.group(2) != m.group(3):
            return on_error(utils.lineno())
        result = database.Result(int(m.group(2)), int(m.group(3)), int(m.group(4)))
    else:
        result = database.Result(int(m.group(2)), int(m.group(3)))

    if not result.winner and match.is_playoff():
        keyboard = telebot.types.InlineKeyboardMarkup(row_width=1)
        keyboard.add(
            telebot.types.InlineKeyboardButton(
                match.team(0).flag() + match.team(0).name(), callback_data=data + "_1"
            )
        )
        keyboard.add(
            telebot.types.InlineKeyboardButton(
                match.team(1).flag() + match.team(1).name(), callback_data=data + "_2"
            )
        )
        if EXTRA_SCORE_MODE == "extratime":
            return edit_message(messages.EXTRA_WINNER_REQUEST, reply_markup=keyboard)
        else:
            return edit_message(messages.PENALTY_WINNER_REQUEST, reply_markup=keyboard)

    unow = utils.utcnow()
    if match.start_time() < unow:
        return edit_message(messages.TOO_LATE_MSG % RESULTS_URL)

    logger.info(
        "prediction player: %s match: %s result: %s time: %s"
        % (player.id(), match.id(), str(result), unow)
    )
    db.predictions.addPrediction(player, match, result, unow)
    start_time_str = (
        match.start_time().astimezone(player.tz()).strftime("%d.%m в %H:%M")
    )
    bet_time_str = unow.astimezone(player.tz()).strftime("%d.%m в %H:%M:%S")
    msg = messages.CONFIRMATION_MSG % (
        match.label(result),
        bet_time_str,
        start_time_str,
        player.short_name(),
        RESULTS_URL,
    )
    return edit_message(msg)


class UpdateJob:
    MATCHES_TO_NOTIFY = None
    MATCHES_IN_PROGRESS = None
    MATCHES_TO_REMIND = None
    MATCHES_DAY_TO_REMIND = None

    MATCH_PROCESSED_EVENTS = defaultdict(list)

    @classmethod
    def init_update_job(cls):
        logger.info("Init regular update job")
        db_helper.reload_db()
        db = db_helper.get_db()

        unow = utils.utcnow()
        cls.MATCHES_TO_NOTIFY = {m.id() for m in db.matches.getMatchesAfter(unow)}
        logger.info(f"Found matches to notify: {cls.MATCHES_TO_NOTIFY}")
        cls.MATCHES_IN_PROGRESS = {
            m.id() for m in db.matches.getMatchesBefore(unow) if not m.is_finished()
        }
        logger.info(f"Found matches in progress: {cls.MATCHES_IN_PROGRESS}")
        cls.MATCHES_TO_REMIND = {
            m.id() for m in db.matches.getMatchesAfter(unow + REMIND_BEFORE)
        }
        logger.info(f"Found matches to remind: {cls.MATCHES_TO_REMIND}")
        cls.MATCHES_DAY_TO_REMIND = {
            m.id() for m in db.matches.getMatchesAfter(unow + REMIND_DAY_BEFORE)
        }
        logger.info(f"Found matches day to remind: {cls.MATCHES_DAY_TO_REMIND}")

    def _remind_players(self, db, match, msg):
        for player_id in db.predictions.getMissingPlayers(match.id()):
            player = db.players.getPlayer(player_id)
            keyboard = telebot.types.InlineKeyboardMarkup(row_width=1)
            keyboard.add(helpers.create_match_button(match, player.tz()))
            try:
                bot.send_message(
                    player_id, msg, parse_mode="Markdown", reply_markup=keyboard
                )
            except Exception as err:
                logger.info(
                    "Error sending remind message to player %s: %s", player_id, err
                )
                continue

    def _send_fixture_events(self, db, match):
        logger.info(f"Send fixture events for match {match.id()}")
        events = sources.get_fixture_events(config, match.id())
        for ev in events:
            if ev in self.MATCH_PROCESSED_EVENTS[match.id()]:
                continue
            logger.info("Send unprocessed event %s", ev)
            self.MATCH_PROCESSED_EVENTS[match.id()].append(ev)
            helpers.send_match_event(bot, db, config, match, ev)

    def _update_work(self):
        db_helper.reload_db()
        db = db_helper.get_db()

        # Make automatic bets for bot players
        make_automatic_bot_bets()

        last_update = utils.utcnow()
        results = db.predictions.genResults(last_update)
        results_fpath = conf.get_results_file(config)
        with open(results_fpath, "w") as fp:
            json.dump(results, fp)
            logger.info(f"Results file dumped to: {results_fpath}")

        for m in db.matches.getMatchesBefore(last_update):
            mid = m.id()
            if mid not in self.MATCHES_TO_NOTIFY:
                continue
            self.MATCHES_TO_NOTIFY.remove(mid)
            self.MATCHES_IN_PROGRESS.add(mid)
            logger.info(f"Add match {mid} in progress")
            helpers.send_match_predictions(bot, db, config, m)

        for m in db.matches.getMatchesBefore(last_update + REMIND_BEFORE):
            if m.id() not in self.MATCHES_TO_REMIND:
                continue
            self.MATCHES_TO_REMIND.remove(m.id())
            self._remind_players(db, m, messages.REMIND_MSG)

        for m in db.matches.getMatchesBefore(last_update + REMIND_DAY_BEFORE):
            if m.id() not in self.MATCHES_DAY_TO_REMIND:
                continue
            self.MATCHES_DAY_TO_REMIND.remove(m.id())
            self._remind_players(db, m, messages.REMIND_DAY_MSG)

        finished_matches = []
        finished_playoff_matches = []
        for mid in self.MATCHES_IN_PROGRESS:
            m = db.matches.getMatch(mid)
            if EVENTS_ENABLED:
                try:
                    self._send_fixture_events(db, m)
                except Exception:
                    logger.exception("Error sending fixture events")
            if m.is_finished():
                finished_matches.append(m)
                if m.is_playoff():
                    finished_playoff_matches.append(m)
        self.MATCHES_IN_PROGRESS -= {m.id() for m in finished_matches}
        if finished_matches:
            helpers.send_scores(bot, db, config, finished_matches=finished_matches)
        if PLAYOFF_TABLE_ENABLED and finished_playoff_matches:
            helpers.send_scores(
                bot,
                db,
                config,
                finished_matches=finished_playoff_matches,
                is_playoff=True,
            )
        logger.info("update finished")

    def __call__(self):
        logger.info("Start regular update job")
        try:
            self._update_work()
        except Exception:
            logger.error(traceback.format_exc())


def start():
    threading.Thread(
        target=bot.infinity_polling, name="bot_infinity_polling", daemon=True
    ).start()

    UpdateJob.init_update_job()
    job = UpdateJob()
    job()
    schedule.every(UPDATE_INTERVAL_SEC).seconds.do(job)
    while True:
        schedule.run_pending()
        time.sleep(1)
