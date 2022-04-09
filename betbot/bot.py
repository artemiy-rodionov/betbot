#!/usr/bin/env python
"""
Created on Sat Jun 04 12:05:50 2016

@author: SSundukov
"""
import json
import logging
import re
import datetime
import time
import traceback
import threading

import pytz
import tabulate
import schedule
import telebot

from config import config
from . import conf, helpers, database, messages, utils, commands

telebot.logger.setLevel(logging.DEBUG)

UPDATE_INTERVAL_SEC = 60
REMIND_BEFORE = datetime.timedelta(minutes=30)
REMIND_DAY_BEFORE = datetime.timedelta(hours=24)

RESULTS_URL = config['results_url']

MSK_TZ = pytz.timezone('Europe/Moscow')

bot = telebot.TeleBot(config["token"])


class DbHelper:
    def __init__(self):
        self._config = config
        self.db_lock = threading.Lock()
        self.db = database.Database(config)

    def get_db(self):
        with self.db_lock:
            return self.db

    def reload_db(self):
        with self.db_lock:
            self.db.reload_data()

    def register_player(self, player):
        assert(not self.is_registered(player))
        logging.info(f'Register player {player}')
        return self.get_db().players.createPlayer(player.id, player.first_name, player.last_name)

    def get_player(self, player):
        assert(self.is_registered(player))
        return self.get_db().players.getPlayer(player.id)

    def is_registered(self, user):
        return self.get_db().players.isRegistered(user.id)

    def is_admin(self, user):
        return self.get_db().players.isAdmin(user.id)


db_helper = DbHelper()


@bot.message_handler(commands=['scores'])
def scores(message):
    helpers.send_scores(bot, db_helper.get_db(), config, reply_message=message)


@bot.message_handler(commands=['send_last'], func=lambda m: db_helper.is_admin(m.from_user))
def send_last(message):
    for m in db_helper.get_db().matches.getMatchesBefore(utils.utcnow()):
        if m.is_finished():
            continue
        helpers.send_match_predictions(bot, db_helper.get_db(), config, m)


@bot.message_handler(
    commands=['final_scores'], func=lambda m: db_helper.is_admin(m.from_user)
)
def send_final_scores(message):
    reply_message = message
    unow = utils.utcnow()
    results = db_helper.get_db().predictions.genResults(unow, verbose=True)
    headers = ['Место', 'Имя', 'Очки', 'Точный счет', 'Разница', 'Победитель', 'Пенальти']
    stats = []
    for idx, player in enumerate(results['players'].values()):
        is_queen = ' ♛ ' if player['is_queen'] else ' '
        stats.append([
            idx+1,
            player['name'] + is_queen,
            player['score'],
            len([p for p in player['predictions'] if p['is_exact_score']]),
            len([
                p for p in player['predictions']
                if p.get('is_difference_score', False)
            ]),
            len([
                p for p in player['predictions']
                if p.get('is_winner_score', False)
            ]),
            len([
                p for p in player['predictions']
                if p.get('is_penalty_score', False)
            ]),
        ])
    text = '\nФинальная Таблица: \n'
    text += '\n```\n'
    text += tabulate.tabulate(stats, headers, tablefmt="pretty")
    text += '\n```\n'

    group_id = message.chat.id
    keyboard = telebot.types.InlineKeyboardMarkup(row_width=1)
    keyboard.add(telebot.types.InlineKeyboardButton(
        messages.CHECK_RESULTS_BUTTON, url=RESULTS_URL
    ))
    bot.send_message(
        group_id,
        text,
        reply_to_message_id=reply_message.message_id if reply_message else None,
        parse_mode='Markdown',
        reply_markup=keyboard,
    )


@bot.message_handler(
    commands=['chart_race'], func=lambda m: db_helper.is_admin(m.from_user)
)
def send_chart_race(message):
    fpath = conf.get_chart_race_file(config)
    with open(fpath, 'rb') as fp:
        video_data = fp.read()
    group_id = message.chat.id
    bot.send_video(group_id, video_data)


@bot.message_handler(commands=['bet'], func=lambda m: m.chat.type != 'private')
def bet_cmd_public_err(message):
    cfg = config
    msg = f'{messages.SEND_PRIVATE_MSG} {cfg["bot_name"]}'
    bot.send_message(
        message.chat.id, msg, reply_to_message_id=message.message_id
    )


@bot.message_handler(func=lambda m: m.chat.type != 'private')
def on_not_private(message):
    pass
    # bot.send_message(
    #     message.chat.id, SEND_PRIVATE_MSG, reply_to_message_id=message.message_id
    # )


@bot.message_handler(
    commands=['register_admin'], func=lambda m: db_helper.is_admin(m.from_user)
)
def register_admin(message):
    user = message.from_user
    if db_helper.is_registered(user):
        player = db_helper.get_player(user)
        bot.send_message(
            message.chat.id,
            messages.ALREADY_REGISTERED % (player.name(), player.id())
        )
        return
    player = db_helper.register_player(user)
    bot.send_message(
        message.chat.id,
        messages.REGISTRATION_SUCCESS % (player.name(), player.short_name(), player.id())
    )
    bot.send_message(
        player.id(),
        messages.START_MSG % player.short_name() + messages.HELP_MSG % RESULTS_URL,
        parse_mode='Markdown'
    )


@bot.message_handler(commands=['register'], func=lambda m: db_helper.is_admin(m.from_user))
def register(message):
    forward_from = helpers.check_forwarded_from(bot, message)
    if forward_from is None:
        return
    if db_helper.is_registered(forward_from):
        player = db_helper.get_player(forward_from)
        bot.send_message(
            message.chat.id,
            messages.ALREADY_REGISTERED % (player.name(), player.id())
        )
        return
    player = db_helper.register_player(message.reply_to_message.forward_from)
    bot.send_message(
        message.chat.id,
        messages.REGISTRATION_SUCCESS % (player.name(), player.short_name(), player.id())
    )
    bot.send_message(
        player.id(),
        messages.START_MSG % player.short_name() + messages.HELP_MSG % RESULTS_URL,
        parse_mode='Markdown'
    )


@bot.message_handler(commands=['make_queen'], func=lambda m: db_helper.is_admin(m.from_user))
def make_queen(message):
    helpers.change_queen(bot, db_helper, message, True)


@bot.message_handler(commands=['unmake_queen'], func=lambda m: db_helper.is_admin(m.from_user))
def unmake_queen(message):
    helpers.change_queen(message, False)


@bot.message_handler(
    commands=['update_fixtures'], func=lambda m: db_helper.is_admin(m.from_user)
)
def cmd_update_fixtures(message):
    commands.update_fixtures(config)
    msg = str(db_helper.get_db().matches)
    bot.send_message(message.chat.id, msg)


@bot.message_handler(func=lambda m: not db_helper.is_registered(m.from_user))
def on_not_registered(message):
    msg = messages.NOT_REGISTERED.format(admin_name=config['admin_name'])
    bot.send_message(message.chat.id, msg)


@bot.message_handler(commands=['bet'])
def start_betting(message):
    db_helper.reload_db()
    player = db_helper.get_player(message.from_user)
    page_to_send = helpers.create_matches_page(db_helper.get_db(), 0, player)
    if page_to_send is None:
        bot.send_message(message.chat.id, messages.NO_MATCHES_MSG)
        return
    title, keyboard = page_to_send
    bot.send_message(message.chat.id, title, reply_markup=keyboard)


@bot.message_handler(commands=['mybets'])
def list_my_bets(message):
    player = db_helper.get_player(message.from_user)
    predictions = db_helper.get_db().predictions.getForPlayer(player)

    if len(predictions) == 0:
        bot.send_message(message.chat.id, messages.NO_BETS_MSG)
        return

    lines = []
    for m, r in predictions:
        lines.append('%s: %s' % (m.short_round(), m.label(r, short=True)))
    lines.append(messages.PRESS_BET + ' ' + messages.RESULTS_TABLE % RESULTS_URL)
    bot.send_message(message.chat.id, '\n'.join(lines), parse_mode='Markdown')


# keep last
@bot.message_handler(func=lambda m: True)
def help(message):
    bot.send_message(
        message.chat.id, messages.HELP_MSG % RESULTS_URL, parse_mode='Markdown'
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
            show_alert=True
        )
        return
    bot.answer_callback_query(callback_query_id=query.id)
    player = db_helper.get_player(query.from_user)
    data = query.data or ''

    db = db_helper.get_db()

    def edit_message(text, **kwargs):
        bot.edit_message_text(
            text,
            chat_id=query.message.chat.id,
            message_id=query.message.message_id,
            parse_mode='Markdown',
            **kwargs
        )

    def on_error(line_no):
        edit_message(messages.NAVIGATION_ERROR % (line_no, RESULTS_URL))

    m = re.match(r'^b_([^_]*)$', data) or \
        re.match(r'^b_([^_]*)_([0-9])$', data) or \
        re.match(r'^b_([^_]*)_([0-9])_([0-9])$', data) or \
        re.match(r'^b_([^_]*)_([0-9])_([0-9])_([12])$', data)

    if m is None:
        m = re.match(r'^l_([0-9]+)$', data)
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
            cb_data = data + '_%d' % score
            return telebot.types.InlineKeyboardButton(str(score), callback_data=cb_data)

        keyboard = telebot.types.InlineKeyboardMarkup(row_width=3)
        keyboard.row(make_button(0))\
            .row(make_button(1), make_button(2), make_button(3))\
            .row(make_button(4), make_button(5), make_button(6))\
            .row(make_button(7), make_button(8), make_button(9))
        team = match.team(0) if args_len == 1 else match.team(1)
        return edit_message(
            messages.SCORE_REQUEST % (team.flag(), team.name()),
            reply_markup=keyboard
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
        keyboard.add(telebot.types.InlineKeyboardButton(
            match.team(0).flag() + match.team(0).name(), callback_data=data + "_1"))
        keyboard.add(telebot.types.InlineKeyboardButton(
            match.team(1).flag() + match.team(1).name(), callback_data=data + "_2"))
        return edit_message(messages.WINNER_REQUEST, reply_markup=keyboard)

    unow = utils.utcnow()
    if match.start_time() < unow:
        return edit_message(messages.TOO_LATE_MSG % RESULTS_URL)

    logging.info(
        'prediction player: %s match: %s result: %s time: %s' % (
            player.id(), match.id(), str(result), unow
        )
    )
    db.predictions.addPrediction(player, match, result, unow)
    start_time_str = match.start_time().astimezone(MSK_TZ).strftime('%d.%m в %H:%M')
    bet_time_str = unow.astimezone(MSK_TZ).strftime('%d.%m в %H:%M:%S')
    msg = messages.CONFIRMATION_MSG % (
        match.label(result),
        bet_time_str, start_time_str, player.short_name(), RESULTS_URL
    )
    return edit_message(msg)


class UpdateJob:
    LAST_UPDATE = None
    MATCHES_TO_NOTIFY = None
    MATCHES_IN_PROGRESS = None
    MATCHES_TO_REMIND = None
    MATCHES_DAY_TO_REMIND = None

    @classmethod
    def init_update_job(cls):
        logging.info("Init regular update job")
        db_helper.reload_db()
        db = db_helper.get_db()

        unow = utils.utcnow()
        cls.LAST_UPDATE = unow - datetime.timedelta(seconds=UPDATE_INTERVAL_SEC)
        cls.MATCHES_TO_NOTIFY = {m.id() for m in db.matches.getMatchesAfter(unow)}
        cls.MATCHES_IN_PROGRESS = {
            m.id() for m in db.matches.getMatchesBefore(unow)
            if not m.is_finished()
        }
        logging.info(f'Found matches in progress: {cls.MATCHES_IN_PROGRESS}')
        cls.MATCHES_TO_REMIND = {
            m.id() for m in db.matches.getMatchesAfter(unow + REMIND_BEFORE)
        }
        cls.MATCHES_DAY_TO_REMIND = {
            m.id() for m in db.matches.getMatchesAfter(unow + REMIND_DAY_BEFORE)
        }

    def _update_work(self):
        db_helper.reload_db()
        db = db_helper.get_db()

        last_update = utils.utcnow()
        results = db.predictions.genResults(last_update)
        results_fpath = conf.get_results_file(config)
        with open(results_fpath, 'w') as fp:
            json.dump(results, fp)
            logging.info('Results file dumped')

        for m in db.matches.getMatchesBefore(last_update):
            mid = m.id()
            if mid not in self.MATCHES_TO_NOTIFY:
                continue
            self.MATCHES_TO_NOTIFY.remove(mid)
            self.MATCHES_IN_PROGRESS.add(mid)
            logging.info(f'Add match {mid} in progress')
            helpers.send_match_predictions(bot, db, config, m)

        for m in db.matches.getMatchesBefore(last_update + REMIND_BEFORE):
            if m.id() not in self.MATCHES_TO_REMIND:
                continue
            self.MATCHES_TO_REMIND.remove(m.id())
            for player_id in db.predictions.getMissingPlayers(m.id()):
                keyboard = telebot.types.InlineKeyboardMarkup(row_width=1)
                keyboard.add(helpers.create_match_button(m))
                bot.send_message(
                    player_id,
                    messages.REMIND_MSG,
                    parse_mode='Markdown',
                    reply_markup=keyboard
                )

        for m in db.matches.getMatchesBefore(last_update + REMIND_DAY_BEFORE):
            if m.id() not in self.MATCHES_DAY_TO_REMIND:
                continue
            self.MATCHES_DAY_TO_REMIND.remove(m.id())
            for player_id in db.predictions.getMissingPlayers(m.id()):
                keyboard = telebot.types.InlineKeyboardMarkup(row_width=1)
                keyboard.add(helpers.create_match_button(m))
                bot.send_message(
                    player_id,
                    messages.REMIND_DAY_MSG,
                    parse_mode='Markdown',
                    reply_markup=keyboard
                )
        finished_matches = []
        for mid in self.MATCHES_IN_PROGRESS:
            m = db.matches.getMatch(mid)
            if m.is_finished():
                finished_matches.append(m)
        self.MATCHES_IN_PROGRESS -= {m.id() for m in finished_matches}
        if finished_matches:
            helpers.send_scores(bot, db, config, finished_matches=finished_matches)
        logging.info('update finished')

    def __call__(self):
        logging.info("Start regular update job")
        try:
            self._update_work()
        except Exception:
            logging.error(traceback.format_exc())


def start():
    threading.Thread(
        target=bot.infinity_polling, name='bot_infinity_polling', daemon=True
    ).start()

    UpdateJob.init_update_job()
    job = UpdateJob()
    job()
    schedule.every(10).seconds.do(job)
    while True:
        schedule.run_pending()
        time.sleep(1)
