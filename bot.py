#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Created on Sat Jun 04 12:05:50 2016

@author: SSundukov
"""

import inspect
import json
import logging
import pytz
import re
import sys
import telebot
import argparse
from datetime import datetime

from database import Database, Result

MATCHES_PER_PAGE = 8
MSK_TZ = pytz.timezone('Europe/Moscow')

BOT_USERNAME = '@delaytevashistavkibot'
HELP_MSG = u'Жми /bet, чтобы сделать новую ставку или изменить существующую. /mybets, чтобы посмотреть свои ставки.'
START_MSG = u'Привет, %s! Поздравляю, ты в игре!\n'
SEND_PRIVATE_MSG = u'Tcccc, не пали контору. Напиши мне личное сообщение (%s).' % BOT_USERNAME
NAVIGATION_ERROR = u'Сорян, что-то пошло не так в строке %d. Попробуй еще раз.\n' + HELP_MSG
NO_MATCHES_MSG = u'Уже не на что ставить =('
SCORE_REQUEST = u'Сколько голов забьет %s%s?'
WINNER_REQUEST = u'Кто победит по пенальти?'
TOO_LATE_MSG = u'Уже поздно ставить на этот матч. Попробуй поставить на другой.\n' + HELP_MSG
CONFIRMATION_MSG = u'Ставка %s%s %s%d:%d%s %s%s сделана %s. Начало матча %s по Москве. Удачи, %s!\n' + HELP_MSG
NO_BETS_MSG = u'Ты еще не сделал(а) ни одной ставки.\n' + HELP_MSG
RESULTS_TITLE = u'Ставки сделаны, ставок больше нет.\n*%s - %s*\n'
CHOOSE_MATCH_TITLE = u'Выбери матч'
LEFT_ARROW = u'\u2b05'
RIGHT_ARROW = u'\u27a1'
BALL = u'\u26bd'
NOT_REGISTERED=u'Ты пока не зарегистрирован(а). Напиши пользователю @dzhioev для получения доступа.'
ALREADY_REGISTERED=u'%s (%s) уже зарегистрирован(а).'
REGISTER_SHOULD_BE_REPLY=u'Сообщение о регистрации должно быть ответом.'
REGISTER_SHOULD_BE_REPLY_TO_FORWARD=u'Сообщение о регистрации должно быть ответом на форвард.'
REGISTRATION_SUCCESS=u'%s aka %s (%s) успешно зарегистрирован.'
ERROR_MESSAGE_ABSENT=u'Этот виджет сломан, вызови /bet снова.'

def lineno():
  return inspect.currentframe().f_back.f_lineno

def utcnow():
  return pytz.utc.localize(datetime.utcnow())

def post_results(config, match_id, post_now=False):
  print 'Spawned process for match %s' % match_id
  telebot.logger.setLevel(logging.INFO)
  db = Database(config)
  match = db.matches.getMatch(match_id)
  if not post_now:
    now = utcnow()
    if now > match.time:
      delay = 0
    else:
      delay = (match.time - now).total_seconds()
    print 'Going to sleep for %s seconds.' % delay
    sleep(delay)
  bot = telebot.TeleBot(config['token'], threaded=False)
  lines = []
  for p, r in db.predictions.getForMatch(match):
    lines.append('_%s_ %s%d - %d%s' % (p.name(), BALL if r.penalty_win1() else '',
                                                 r.goals1,
                                                 r.goals2,
                                                 BALL if r.penalty_win2() else ''))
  msg = RESULTS_TITLE % (match.team1.name, match.team2.name) + '\n'.join(lines)
  bot.send_message(config['group_id'], msg, parse_mode='Markdown')

def main(config, just_dump):
  db = Database(config)
  if just_dump:
    print(str(db.teams))
    print(str(db.matches))
    return

  telebot.logger.setLevel(logging.INFO)
  logging.getLogger().setLevel(logging.INFO)
  # Threading disabled because it is unsupported by sqlite3
  bot = telebot.TeleBot(config['token'], threaded=False)

  def register_player(player):
    assert(not is_registered(player))
    return db.players.createPlayer(player.id, player.first_name, player.last_name)

  def get_player(player):
    assert(is_registered(player))
    return db.players.getPlayer(player.id)

  def is_registered(user):
    return db.players.isRegistered(user.id)

  def is_admin(user):
    return db.players.isAdmin(user.id)

  def create_matches_page(page, player):
    matches = db.matches.getMatchesAfter(utcnow())
    matches_number = len(matches)
    if matches_number == 0:
      return None
    pages_number = (matches_number - 1) / MATCHES_PER_PAGE + 1
    page = min(page, pages_number - 1)
    matches = matches[page * MATCHES_PER_PAGE:(page + 1) * MATCHES_PER_PAGE]
    keyboard = telebot.types.InlineKeyboardMarkup(1)
    predictions = {}
    for m, r in db.predictions.getForPlayer(player):
      predictions[m.id()] = r
    for m in matches:
      start_time_str = m.start_time().astimezone(MSK_TZ).strftime('%d.%m %H:%M')
      if m.id() in predictions:
        p = predictions[m.id()]
        label = u'%s: %s%s %s%d:%d%s %s%s %s' % \
                    (m.short_round(), m.team(0).flag(), m.team(0).short_name(),
                     BALL if p.penalty_win1() else '', p.goals(0), p.goals(1),
                     BALL if p.penalty_win2() else '', m.team(1).short_name(), m.team(1).flag(),
                     start_time_str)
      else:
        label = u'%s: %s%s - %s%s %s' % \
                    (m.short_round(), m.team(0).flag(), m.team(0).short_name(),
                     m.team(1).short_name(), m.team(1).flag(), start_time_str)

      button = telebot.types.InlineKeyboardButton(label,
                                                  callback_data='b_%s' % m.id())
      keyboard.add(button)
    navs = []
    if pages_number > 1:
      navs.append(
          telebot.types.InlineKeyboardButton(
              LEFT_ARROW,
              callback_data='l_%d' % ((page + pages_number - 1) % pages_number)))
      navs.append(
          telebot.types.InlineKeyboardButton(
              '%d/%d' % (page + 1, pages_number),
              callback_data='l_%d' % page))
      navs.append(
          telebot.types.InlineKeyboardButton(
              RIGHT_ARROW,
              callback_data='l_%d' % ((page + 1)  % pages_number)))
      keyboard.row(*navs)
    title = CHOOSE_MATCH_TITLE
    return (title, keyboard)

  @bot.message_handler(func=lambda m: m.chat.type != 'private')
  def on_not_private(message):
    bot.send_message(message.chat.id, SEND_PRIVATE_MSG,
                     reply_to_message_id=message.message_id)

  @bot.message_handler(commands=['register'], func=lambda m: is_admin(m.from_user))
  def register(message):
    if message.reply_to_message is None:
      bot.send_message(message.chat.id, REGISTER_SHOULD_BE_REPLY)
      return
    if message.reply_to_message.forward_from is None:
      bot.send_message(message.chat.id, REGISTER_SHOULD_BE_REPLY_TO_FORWARD)
      return
    forward_from = message.reply_to_message.forward_from
    if is_registered(forward_from):
      player = get_player(forward_from)
      bot.send_message(message.chat.id, ALREADY_REGISTERED % (player.name(), player.id()))
      return
    player = register_player(message.reply_to_message.forward_from)
    bot.send_message(message.chat.id, REGISTRATION_SUCCESS % (player.name(), player.short_name(),
                                                              player.id()))
    bot.send_message(player.id(), START_MSG % player.short_name() + HELP_MSG)

  @bot.message_handler(func=lambda m: not is_registered(m.from_user))
  def on_not_registered(message):
    bot.send_message(message.chat.id, NOT_REGISTERED)

  @bot.message_handler(commands=['bet'])
  def start_betting(message):
    player = get_player(message.from_user)
    page_to_send = create_matches_page(0, player)
    if page_to_send is None:
      bot.send_message(message.chat.id, NO_MATCHES_MSG)
      return
    title, keyboard = page_to_send
    bot.send_message(message.chat.id, title,
                     reply_markup=keyboard)

  @bot.message_handler(commands=['mybets'])
  def list_my_bets(message):
    player = get_player(message.from_user)
    predictions = db.predictions.getForPlayer(player)

    if len(predictions) == 0:
      bot.send_message(message.chat.id, NO_BETS_MSG)
      return

    lines = []
    for m, r in predictions:
      lines.append('%s: %s%s %s%d:%d%s %s%s' %
                       (m.short_round(), m.team(0).flag(), m.team(0).short_name(),
                        BALL if r.penalty_win1() else '', r.goals(0), r.goals(1),
                        BALL if r.penalty_win2() else '', m.team(1).short_name(), m.team(1).flag()))
    bot.send_message(message.chat.id, '\n'.join(lines))

  # keep last
  @bot.message_handler(func=lambda m: True)
  def help(message):
    bot.send_message(message.chat.id, HELP_MSG)

  # l_<page>
  # b_<match_id>
  # b_<match_id>_<goals1>
  # b_<match_id>_<goals1>_<goals2>
  # b_<match_id>_<goals1>_<goals2>_<winner>
  @bot.callback_query_handler(lambda m: True)
  def handle_query(query):
    if query.message is None:
      bot.answer_callback_query(callback_query_id=query.id,
                                text=ERROR_MESSAGE_ABSENT,
                                show_alert=True)
      return
    bot.answer_callback_query(callback_query_id=query.id)
    player = get_player(query.from_user)
    data = query.data or ''

    def edit_message(text, **kwargs):
      bot.edit_message_text(text, chat_id=query.message.chat.id,
                            message_id=query.message.message_id, **kwargs)

    def on_error(line_no):
      edit_message(NAVIGATION_ERROR % line_no)

    m = re.match(r'^b_([^_]*)$', data) or \
        re.match(r'^b_([^_]*)_([0-9])$', data) or \
        re.match(r'^b_([^_]*)_([0-9])_([0-9])$', data) or \
        re.match(r'^b_([^_]*)_([0-9])_([0-9])_([12])$', data)

    if m is None:
      m = re.match(r'^l_([0-9]+)$', data)
      if m is None:
        return on_error(lineno())
      page = int(m.group(1))
      page_to_send = create_matches_page(page, player)
      if page_to_send is None:
        return edit_message(NO_MATCHES_MSG)
      title, keyboard = page_to_send
      return edit_message(title, reply_markup=keyboard)

    match = db.matches.getMatch(int(m.group(1)))
    if match is None:
      return on_error(lineno())

    args_len = len(m.groups())
    if args_len in [1, 2]:
      def make_button(score):
        cb_data = data + '_%d' % score
        return telebot.types.InlineKeyboardButton(str(score), callback_data=cb_data)

      keyboard = telebot.types.InlineKeyboardMarkup(3)
      keyboard.row(make_button(0))\
              .row(make_button(1), make_button(2), make_button(3))\
              .row(make_button(4), make_button(5), make_button(6))\
              .row(make_button(7), make_button(8), make_button(9))
      team = match.team(0) if args_len == 1 else match.team(1)
      return edit_message(SCORE_REQUEST % (team.flag(), team.name()), reply_markup=keyboard)

    if args_len == 4:
      if not match.is_playoff():
        return on_error(lineno())
      if m.group(2) != m.group(3):
        return on_error(lineno())
      result = Result(int(m.group(2)), int(m.group(3)), int(m.group(4)))
    else:
      result = Result(int(m.group(2)), int(m.group(3)))

    if not result.winner and match.is_playoff():
      keyboard = telebot.types.InlineKeyboardMarkup(1)
      keyboard.add(telebot.types.InlineKeyboardButton(
        match.team(0).flag() + match.team(0).name(), callback_data=data + "_1"))
      keyboard.add(telebot.types.InlineKeyboardButton(
        match.team(1).flag() + match.team(1).name(), callback_data=data + "_2"))
      return edit_message(WINNER_REQUEST, reply_markup=keyboard)

    now = utcnow()
    logging.info('prediction player: %s match: %s result: %s time: %s' %
                     (player.id(), match.id(), str(result), now))

    if match.start_time() < now:
      return edit_message(TOO_LATE_MSG)

    db.predictions.addPrediction(player, match, result, now)
    start_time_str = match.start_time().astimezone(MSK_TZ)\
                          .strftime(u'%d.%m в %H:%M'.encode('utf-8')).decode('utf-8')
    bet_time_str = now.astimezone(MSK_TZ)\
                      .strftime(u'%d.%m в %H:%M:%S'.encode('utf-8')).decode('utf-8')
    msg = CONFIRMATION_MSG % (
         match.team(0).flag(), match.team(0).name(), BALL if result.penalty_win1() else '', \
         result.goals(0), result.goals(1), BALL if result.penalty_win2() else '',
         match.team(1).name(), match.team(1).flag(), bet_time_str, start_time_str,
         player.short_name())
    return edit_message(msg)

  bot.polling(none_stop=True)

if __name__ == '__main__':
  parser = argparse.ArgumentParser()
  parser.add_argument('config')
  parser.add_argument('-d', '--dump', help='Print teams and matches and exit',
                      action='store_true')
  args = parser.parse_args(sys.argv[1:])
  with open(args.config) as config_file:
    config = json.load(config_file)
  sys.exit(main(config, args.dump))
