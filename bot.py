# -*- coding: utf-8 -*-
"""
Created on Sat Jun 04 12:05:50 2016

@author: SSundukov
"""

import json
import sys
import telebot
import time
import urllib3
import logging

from database import Database

def send_log(message):
    info = {
        "usr_id": str(message.from_user.id),
        "tag": message.from_user.username,
        "first_name": message.from_user.first_name,
        "last_name": message.from_user.last_name,
        "text": message.text
    }


    if info["last_name"] is not None:
        info["last_name"] = " " + info["last_name"]

    for i in info:
        if info[i] is None:
            info[i] = ""

    time.ctime()

    sys.stdout.write(time.strftime("%X") + " [" + info["tag"] + "][" + info["first_name"] + info["last_name"] + "][" + info["usr_id"] + "] Txt: " + info["text"] + '\n')

    #bot.send_message('chat_id', info["first_name"] + info["last_name"] + " сделал(а) свою ставку")

def main(config):
  telebot.logger.setLevel(logging.DEBUG)
  # Threading disabled because it is unsupported by sqlite3
  bot = telebot.TeleBot(config['token'], threaded=False)
  db = Database(config['db_path'], config['data_dir'])

  @bot.message_handler(commands=['start', 'help'])
  def send_welcome(message):
    msg = bot.send_message(message.chat.id, 'Привет, лудоман! Опять взялся за старое? Просто пиши свои прогнозы на матчи сюда и посмотрим, что из этого получится!')

  @bot.message_handler(commands=['bet'])
  def start_betting(message):
    pass

  @bot.message_handler(content_types=["text"])
  def repeat_all_messages(message): # Название функции не играет никакой роли, в принципе
    id = str(message.from_user.id)
    name = message.from_user.first_name
    if message.from_user.last_name:
      name += ' ' + message.from_user.last_name

    send_log(message)
    bot.reply_to(message, 'Принято!')

  bot.polling(none_stop=True)

if __name__ == '__main__':
  with open(sys.argv[1]) as config_file:
    config = json.load(config_file)
  main(config)
