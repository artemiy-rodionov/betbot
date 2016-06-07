# -*- coding: utf-8 -*-
import sys;
reload(sys);
sys.setdefaultencoding("utf8")
"""
Created on Sat Jun 04 12:05:50 2016

@author: SSundukov
"""


import telebot
import time


bot = telebot.TeleBot('token_id')


def send_log(message):
    info = {
        "usr_id": str(message.from_user.id),
        "tag": message.from_user.username,
        "first_name": message.from_user.first_name,
        "last_name": message.from_user.last_name,
        "text": message.text
    }
 
    #if info["chat_type"] != "private":
    #    info["title"] = "['" + message.chat.title + "']"
 
    if info["last_name"] is not None:
        info["last_name"] = " " + info["last_name"]
 
    for i in info:
        if info[i] is None:
            info[i] = ""
 
    time.ctime() # questo a cosa serve scus?
    #log = pd.read_csv('D:/Misc/telebot/messages.csv')
    f = open('D:/Misc/telebot/log.txt', 'a')

    #txt = log['text'].values
    f.write(time.strftime("%X") + " [" + info["tag"] + "][" + info["first_name"] + info["last_name"] + "][" + info["usr_id"] + "] Txt: " + info["text"] + '\n')
    #l_ar = numpy.array(l)    
    f.close()

        
    bot.send_message('chat_id', info["first_name"] + info["last_name"] + " сделал(а) свою ставку")

@bot.message_handler(commands=['start'])
def send_welcome(message):
    msg = bot.send_message(message.chat.id, 'Привет, лудоман! Опять взялся за старое? Просто пиши свои прогнозы на матчи сюда и посмотрим, что из этого получится!')

@bot.message_handler(commands=['help'])
def send_welcome(message):
    msg = bot.send_message(message.chat.id, 'Просто пиши свои прогнозы на матчи сюда и посмотрим, что из этого получится!')

    
@bot.message_handler(content_types=["text"])
def repeat_all_messages(message): # Название функции не играет никакой роли, в принципе
    #log = pd.read_csv('D:/Misc/foot_pars/seasons_tst.csv' message.from_user.first_name
    send_log(message)     
    bot.reply_to(message, 'Принято!')

if __name__ == '__main__':
    bot.polling(none_stop=True)
