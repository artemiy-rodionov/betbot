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

from database import Database, Result

MATCHES_PER_PAGE = 7

BOT_USERNAME = '@delaytevashistavkibot'
HELP_MSG = u'Жми /bet, чтобы сделать новую ставку или изменить существующую. /mybets, чтобы посмотреть свои ставки'
START_MSG = u'Привет, лудоман! Опять взялся за старое?\n' + HELP_MSG
SEND_PRIVATE_MSG = u'Я не принимаю ставки в открытую. Напиши мне личное сообщение (%s).' % BOT_USERNAME
NAVIGATION_ERROR = u'Сорян, что-то пошло не так в строке %d. Попробуй еще раз.\n' + HELP_MSG
NO_MATCHES_MSG = u'Не на что ставить, сорян.'
SCORE_REQUEST = u'Сколько голов забьет %s?'
WINNER_REQUEST = u'Кто победит по пенальти?'
TOO_LATE_MSG = u'Уже поздно ставить на этот матч, сорян. Попробуй поставить на другой.\n' + HELP_MSG
CONFIRMATION_MSG = u'Ставка %s (%d) - %s (%d) сделана. Начало матча %02d.%02d в %d:%02d по Москве. Удачи, %s!\n' + HELP_MSG
NO_BETS_MSG = u'Ты еще не сделал ни одной ставки.\n' + HELP_MSG
RESULTS_TITLE = u'Ставки сделаны, ставок больше нет.\n*%s - %s*\n'
CHOOSE_MATCH_TITLE = u'Выбери матч (%d/%d)'
LEFT_ARROW = u'\u2b05'
RIGHT_ARROW = u'\u27a1'

def lineno():
  return inspect.currentframe().f_back.f_lineno

def utcnow():
  return pytz.utc.localize(datetime.utcnow())

def post_results(config, match_id):
  print 'Spawned process for match %s' % match_id
  telebot.logger.setLevel(logging.DEBUG)
  db = Database(config['db_path'], config['data_dir'])
  match = db.matches.getMatch(match_id)
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
    lines.append('_%s_ %d - %d' % (p.name, r.goals1, r.goals2))
  msg = RESULTS_TITLE % (match.team1.name, match.team2.name) + '\n'.join(lines)
  bot.send_message(config['group_id'], msg, parse_mode='Markdown')

def main(config):
  telebot.logger.setLevel(logging.DEBUG)

  db = Database(config['db_path'], config['data_dir'])
  for match in db.matches.getMatchesAfter(utcnow()):
    multiprocessing.Process(
        target=post_results, args=(config, match.id)).start();

  # Threading disabled because it is unsupported by sqlite3
  bot = telebot.TeleBot(config['token'], threaded=False)

  def register_player(player):
    return db.players.getOrCreatePlayer(player.id,
                                        player.first_name,
                                        player.last_name)

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
        label = "%s %d - %d %s %02d.%02d %d:%02d" % \
                    (m.team1.id, predictions[m.id].goals1,
                     predictions[m.id].goals2, m.team2.id,
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

  @bot.message_handler(commands=['start'])
  def send_welcome(message):
    register_player(message.from_user)
    bot.send_message(message.chat.id, START_MSG)

  @bot.message_handler(commands=['bet'])
  def start_betting(message):
    if message.chat.type != 'private':
      bot.send_message(message.chat.id, SEND_PRIVATE_MSG,
                       reply_to_message_id=message.message_id)
      return

    player = register_player(message.from_user)
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

    player = register_player(message.from_user)
    predictions = db.predictions.getForPlayer(player)

    if len(predictions) == 0:
      bot.send_message(message.chat.id, NO_BETS_MSG)
      return

    msk_tz = pytz.timezone('Europe/Moscow')
    lines = []
    for m, r in predictions:
      t = m.time.astimezone(msk_tz)
      lines.append('%02d.%02d %s %d - %d %s' % (t.day, t.month,
                                                m.team1.name, r.goals1,
                                                r.goals2, m.team2.name))
    bot.send_message(message.chat.id, '\n'.join(lines))

  @bot.message_handler(func=lambda m: True)
  def help(message):
    register_player(message.from_user)
    bot.send_message(message.chat.id, HELP_MSG)

  # l_<page> (not implemented, needed for pages navigation)
  # b_<match_id>
  # b_<match_id>_<goals1>
  # b_<match_id>_<goals1>_<goals2>
  # b_<match_id>_<goals1>_<goals2>_<winner> (not implemented,
  #                                          needed for playoff)
  @bot.callback_query_handler(lambda m: True)
  def handle_navigation(message):
    player = register_player(message.from_user)
    data = message.data or ''

    m = re.match(r'^b_([^_]*)$', data) or \
        re.match(r'^b_([^_]*)_([0-9])$', data) or \
        re.match(r'^b_([^_]*)_([0-9])_([0-9])$', data)

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
      if page_to_send is None:
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

    if len(m.groups()) in [1, 2]:
      def make_button(score):
        cb_data = data + '_%d' % score
        return telebot.types.InlineKeyboardButton(
            str(score), callback_data=cb_data)

      keyboard = telebot.types.InlineKeyboardMarkup(3)
      keyboard.row(make_button(0))\
              .row(make_button(1), make_button(2), make_button(3))\
              .row(make_button(4), make_button(5), make_button(6))\
              .row(make_button(7), make_button(8), make_button(9))
      team = match.team1 if len(m.groups()) == 1 else match.team2
      bot.edit_message_text(SCORE_REQUEST % team.name,
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

    result = Result(int(m.group(2)), int(m.group(3)))
    db.predictions.addPrediction(player, match, result, now)

    t = match.time.astimezone(pytz.timezone('Europe/Moscow'))
    msg = CONFIRMATION_MSG % (match.team1.name, result.goals1, match.team2.name,
                              result.goals2, t.day, t.month, t.hour, t.minute,
                              player.first_name)
    bot.edit_message_text(msg,
                          chat_id=message.message.chat.id,
                          message_id=message.message.message_id)

  bot.polling(none_stop=True)

if __name__ == '__main__':
  with open(sys.argv[1]) as config_file:
    config = json.load(config_file)
  main(config)
