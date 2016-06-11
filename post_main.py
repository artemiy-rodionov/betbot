# -*- coding: utf-8 -*-

"""
Created on Sat Jun 04 12:05:50 2016

@author: SSundukov
"""

import telebot


bot = telebot.TeleBot('token_id')

f = open('D:/Misc/telebot/log.txt', 'r+')
f1 = open('D:/Misc/telebot/log_hist.txt', 'a')
l = f.readlines()
f1.writelines(l)
mes = ''
for i, line in enumerate(l):
    mes = mes + line + '\n'
    if i%30 == 0 & i > 0:
        bot.send_message(-110462515, mes)
        mes = ''
        
print mes

f.truncate(0)
f.close()
f1.close()
bot.send_message('chat_id', mes)