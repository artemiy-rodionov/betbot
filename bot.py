# -*- coding: utf-8 -*-
"""
Created on Sat Jun 04 12:05:50 2016

@author: SSundukov
"""

import json
import logging
import pytz
import sys
import telebot
import time
import urllib3
from datetime import datetime

from database import Database

BOT_USERNAME = '@delaytevashistavkibot'
START_MSG = 'Привет, лудоман! Опять взялся за старое? Жми /bet чтобы сделать ставку'
HELP_MSG = 'Жми /bet чтобы сделать ставку'
SEND_PRIVATE_MSG = 'Я не принимаем ставки в открытую. Напиши мне личное сообщение (%s)' % BOT_USERNAME

def main(config):
  telebot.logger.setLevel(logging.DEBUG)
  # Threading disabled because it is unsupported by sqlite3
  bot = telebot.TeleBot(config['token'], threaded=False)
  db = Database(config['db_path'], config['data_dir'])

  def register_user(user):
    return db.players.getOrCreatePlayer(user.id, user.first_name, user.last_name)

  @bot.message_handler(commands=['start'])
  def send_welcome(message):
    register_user(message.from_user)
    bot.send_message(message.chat.id, START_MSG)

  @bot.message_handler(commands=['bet'])
  def start_betting(message):
    if message.chat.type != 'private':
      bot.send_message(message.chat.id, SEND_PRIVATE_MSG,
                       reply_to_message_id=message.id)
      return

    register_user(message.from_user)

    matches = db.matches.getMatchesAfter(
                  datetime.fromtimestamp(message.date, pytz.utc))
    keyboard = telebot.types.InlineKeyboardMarkup(2)
    msk_tz = pytz.timezone('Europe/Moscow')
    buttons = []
    for m in matches:
      t = m.time.astimezone(msk_tz)
      #label = "%s - %s %02d.%02d %d:%02d" % \
      #            (m.team1.id, m.team2.id, t.day, t.month, t.hour, t.minute)
      label = "%s - %s %02d.%02d" % \
                  (m.team1.id, m.team2.id, t.day, t.month)
      button = telebot.types.InlineKeyboardButton(label, callback_data='42')
      buttons.append(button)
    keyboard.add(*buttons)
    bot.send_message(message.chat.id, 'Выбери матч', reply_markup=keyboard)


  @bot.message_handler(func=lambda m: True)
  def help(message):
    register_user(message.from_user)
    bot.send_message(message.chat.id, HELP_MSG)


  bot.polling(none_stop=True)

if __name__ == '__main__':
  with open(sys.argv[1]) as config_file:
    config = json.load(config_file)
  main(config)
