# -*- coding: utf-8 -*-

import json
import sys

import bot

with open(sys.argv[1]) as c:
  config = json.load(c)
match_id = sys.argv[2]
bot.post_results(config, match_id, True)
