# -*- coding: utf-8 -*-
"""
Created on Sat Jun 04 12:05:50 2016

@author: SSundukov
"""

import inspect
import json
import logging
import multiprocessing
import pytz
import re
import sys
import telebot
import time
import urllib3
from datetime import datetime
from time import sleep
from pprint import pprint

from database import Database, Result

MATCHES_PER_PAGE = 7

BOT_USERNAME = '@delaytevashistavkibot'
HELP_MSG = u'Жми /bet, чтобы сделать новую ставку или изменить существующую. /mybets, чтобы посмотреть свои ставки'
START_MSG = u'Привет, %s! Поздравляю, ты в игре!\n'
SEND_PRIVATE_MSG = u'Tcccc, не пали контору. Напиши мне личное сообщение (%s).' % BOT_USERNAME
NAVIGATION_ERROR = u'Сорян, что-то пошло не так в строке %d. Попробуй еще раз.\n' + HELP_MSG
NO_MATCHES_MSG = u'Уже не на что ставить =('
SCORE_REQUEST = u'Сколько голов забьет %s?'
WINNER_REQUEST = u'Кто победит по пенальти?'
TOO_LATE_MSG = u'Уже поздно ставить на этот матч. Попробуй поставить на другой.\n' + HELP_MSG
CONFIRMATION_MSG = u'Ставка %s %s%d - %d%s %s сделана. Начало матча %02d.%02d в %d:%02d по Москве. Удачи, %s!\n' + HELP_MSG
NO_BETS_MSG = u'Ты еще не сделал(а) ни одной ставки.\n' + HELP_MSG
RESULTS_TITLE = u'Ставки сделаны, ставок больше нет.\n*%s - %s*\n'
CHOOSE_MATCH_TITLE = u'Выбери матч (%d/%d)'
LEFT_ARROW = u'\u2b05'
RIGHT_ARROW = u'\u27a1'
BALL = u'\u26bd'
NOT_REGISTERED=u'Ты пока не зарегистрирован(а). Напиши пользователю @dzhioev для получения доступа.'
ALREADY_REGISTERED=u'%s (%s) уже зарегистрирован(а).'
REGISTER_SHOULD_BE_REPLY=u'Сообщение о регистрации должно быть ответом.'
REGISTER_SHOULD_BE_REPLY_TO_FORWARD=u'Сообщение о регистрации должно быть ответом на форвард.'
REGISTRATION_SUCCESS=u'%s aka %s (%s) успешно зарегистрирован.'

def lineno():
  return inspect.currentframe().f_back.f_lineno

def utcnow():
  return pytz.utc.localize(datetime.utcnow())

def post_results(config, match_id, post_now=False):
  print 'Spawned process for match %s' % match_id
  telebot.logger.setLevel(logging.INFO)
  db = Database(config['db_path'], config['data_dir'])
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

def main(config):
  telebot.logger.setLevel(logging.INFO)

  db = Database(config['db_path'], config['data_dir'])
  for match in db.matches.getMatchesAfter(utcnow()):
    multiprocessing.Process(
        target=post_results, args=(config, match.id)).start();

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
    msk_tz = pytz.timezone('Europe/Moscow')
    predictions = {}
    for m, r in db.predictions.getForPlayer(player):
      predictions[m.id] = r
    for m in matches:
      t = m.time.astimezone(msk_tz)
      if m.id in predictions:
        p = predictions[m.id]
        label = "%s %s%d - %d%s %s %02d.%02d %d:%02d" % \
                    (m.team1.id, BALL if p.penalty_win1() else '', p.goals1,
                     p.goals2, BALL if p.penalty_win2() else '', m.team2.id,
                     t.day, t.month, t.hour, t.minute)
      else:
        label = "%s - %s %02d.%02d %d:%02d" % \
                    (m.team1.id, m.team2.id, t.day, t.month, t.hour, t.minute)

      button = telebot.types.InlineKeyboardButton(label,
                                                  callback_data='b_%s' % m.id)
      keyboard.add(button)
    navs = []
    if page:
      navs.append(
          telebot.types.InlineKeyboardButton(LEFT_ARROW,
                                             callback_data='l_%d' % (page - 1)))
    if page != pages_number - 1:
      navs.append(
          telebot.types.InlineKeyboardButton(RIGHT_ARROW,
                                             callback_data='l_%d' % (page + 1)))
    if len(navs):
      keyboard.row(*navs)
    title = CHOOSE_MATCH_TITLE % (page + 1, pages_number)
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
    if message.chat.type != 'private':
      bot.send_message(message.chat.id, SEND_PRIVATE_MSG,
                       reply_to_message_id=message.message_id)
      return

    player = get_player(message.from_user)
    predictions = db.predictions.getForPlayer(player)

    if len(predictions) == 0:
      bot.send_message(message.chat.id, NO_BETS_MSG)
      return

    msk_tz = pytz.timezone('Europe/Moscow')
    lines = []
    for m, r in predictions:
      t = m.time.astimezone(msk_tz)
      lines.append('%02d.%02d %s %s%d - %d%s %s' % (t.day, t.month,
                       m.team1.name, BALL if r.penalty_win1() else '', r.goals1,
                       r.goals2, BALL if r.penalty_win2() else '', m.team2.name))
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
  def handle_navigation(message):
    player = get_player(message.from_user)
    data = message.data or ''

    m = re.match(r'^b_([^_]*)$', data) or \
        re.match(r'^b_([^_]*)_([0-9])$', data) or \
        re.match(r'^b_([^_]*)_([0-9])_([0-9])$', data) or \
        re.match(r'^b_([^_]*)_([0-9])_([0-9])_([12])$', data)

    def on_error(line_no):
      bot.edit_message_text(NAVIGATION_ERROR % line_no,
                            chat_id=message.message.chat.id,
                            message_id=message.message.message_id)

    if m is None:
      m = re.match(r'^l_([0-9]+)$', data)
      if m is None:
        on_error(lineno())
        return
      page = int(m.group(1))

      page_to_send = create_matches_page(page, player)
      if page is None:
        bot.edit_message_text(NO_MATCHES_MSG,
                              chat_id=message.message.chat.id,
                              message_id=message.message.message_id)
        return
      title, keyboard = page_to_send
      bot.edit_message_text(title,
                            chat_id=message.message.chat.id,
                            message_id=message.message.message_id,
                            reply_markup=keyboard)
      return

    match = db.matches.getMatch(m.group(1))

    if match is None:
      on_error(lineno())
      return

    args_len = len(m.groups())

    if args_len in [1, 2]:
      def make_button(score):
        cb_data = data + '_%d' % score
        return telebot.types.InlineKeyboardButton(
            str(score), callback_data=cb_data)

      keyboard = telebot.types.InlineKeyboardMarkup(3)
      keyboard.row(make_button(0))\
              .row(make_button(1), make_button(2), make_button(3))\
              .row(make_button(4), make_button(5), make_button(6))\
              .row(make_button(7), make_button(8), make_button(9))
      team = match.team1 if args_len == 1 else match.team2
      bot.edit_message_text(SCORE_REQUEST % team.name,
                            chat_id=message.message.chat.id,
                            message_id=message.message.message_id,
                            reply_markup=keyboard)
      return

    if args_len == 4:
      if not match.is_playoff:
        on_error(lineno())
        return
      if m.group(2) != m.group(3):
        on_error(lineno())
        return
      result = Result(int(m.group(2)), int(m.group(3)), int(m.group(4)))
    else:
      result = Result(int(m.group(2)), int(m.group(3)))

    if not result.winner and match.is_playoff:
      keyboard = telebot.types.InlineKeyboardMarkup(1)
      keyboard.add(telebot.types.InlineKeyboardButton(
        match.team1.name, callback_data=data + "_1"))
      keyboard.add(telebot.types.InlineKeyboardButton(
        match.team2.name, callback_data=data + "_2"))
      bot.edit_message_text(WINNER_REQUEST,
                            chat_id=message.message.chat.id,
                            message_id=message.message.message_id,
                            reply_markup=keyboard)
      return

    now = utcnow()
    if match.time < now:
      bot.edit_message_text(TOO_LATE_MSG,
                            chat_id=message.message.chat.id,
                            message_id=message.message.message_id)
      return

    db.predictions.addPrediction(player, match, result, now)

    t = match.time.astimezone(pytz.timezone('Europe/Moscow'))
    msg = CONFIRMATION_MSG % (
         match.team1.name, BALL if result.penalty_win1() else '', result.goals1,
         result.goals2, BALL if result.penalty_win2() else '', match.team2.name,
         t.day, t.month, t.hour, t.minute, player.short_name())
    bot.edit_message_text(msg,
                          chat_id=message.message.chat.id,
                          message_id=message.message.message_id)

  bot.polling(none_stop=True)

if __name__ == '__main__':
  with open(sys.argv[1]) as config_file:
    config = json.load(config_file)
  main(config)
