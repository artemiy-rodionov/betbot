# -*- coding: utf-8 -*-

import csv
import datetime
import os
import pytz
import re
import sqlite3

def create_csv_reader(iterable):
  return csv.DictReader(filter(lambda row: len(row) > 0 and row[0] != '#',
                               iterable))

class Database(object):
  def __init__(self, db_path, data_dir):
    self.conn = sqlite3.connect(db_path, detect_types=sqlite3.PARSE_DECLTYPES|
                                                      sqlite3.PARSE_COLNAMES)
    self.teams = Teams(os.path.join(data_dir, Teams.DATA_FILENAME))
    self.matches = Matches(os.path.join(data_dir, Matches.DATA_FILENAME),
                           self.teams)
    self.players = Players(self.conn)
    self.predictions = Predictions(self.conn, self.players, self.matches)

class Team(object):
  def __init__(self, id, name, group):
    self.id = id
    self.name = name
    self.group = group

  def __str__(self):
    return "%s (%s) Group %s" % (self.name, self.id, self.group)

class Teams(object):
  DATA_FILENAME = 'teams.csv'

  def __init__(self, data_path):
    self.teams = dict()
    with open(data_path) as table:
      for row in create_csv_reader(table):
        self.teams[row['id']] = Team(**row)

  def __str__(self):
     return '\n'.join(str(t) for t in self.teams.values())

  def get_team(self, team_id):
    return self.teams[team_id]

class Match(object):
  def __init__(self, id, team1, team2, time):
    self.id = id
    self.team1 = team1
    self.team2 = team2
    self.time = time

  def __str__(self):
    return "%d: %s - %s (%s)" % \
               (self.id, self.team1.id, self.team2.id, self.time)

class Matches(object):
  DATA_FILENAME = 'matches.csv'

  def __init__(self, data_path, teams):
    self.matches = dict()
    id = 0
    cest_tz = pytz.timezone('Europe/Berlin')
    with open(data_path) as table:
      for row in create_csv_reader(table):
        team1 = teams.get_team(row['team1'])
        team2 = teams.get_team(row['team2'])
        time = cest_tz.localize(
            datetime.datetime.strptime(row['time'], '%d %B %Y %H:%M'))
        time = time.astimezone(pytz.utc)
        self.matches[id] = Match(id, team1, team2, time)
        id += 1

  def __str__(self):
     return '\n'.join(str(m) for m in self.matches.values())

class Player(object):
  def __init__(self, id, name):
    self.id = id
    self.name = name

  def __str__(self):
    return "%s (%s)" % (self.name, self.id)

class Players(object):
  def __init__(self, conn):
    self.conn = conn
    self.conn.execute('''CREATE TABLE IF NOT EXISTS players
                         (id text, name text)''')
    self.conn.commit()

  def getOrCreatePlayer(self, id, name=None):
    res = self.conn.execute('''SELECT name FROM players WHERE id=?''', (id,))
    rows = [r for r in res]
    if len(rows) == 0:
      if name is None:
        raise Exception('Unknown user %s' % id)
      self.conn.execute('''INSERT INTO players (id, name) VALUES (?,?)''',
                        (id, name))
    else:
      db_saved_name = rows[0][0]
      if name is None:
        name = db_saved_name
      elif db_saved_name != name:
        self.conn.execute('''UPDATE players SET name=? WHERE id=?''', (name, id))
    self.conn.commit()
    return Player(id, name)

def Result(object):
  def __init__(self, goals1, goals2, winner):
    self.goals1 = goals1
    self.goals2 = goals2
    self.winner = winner

def adapt_result(result):
  return "%d - %d (%d)" % (result.goals1, result.goals2, result.winner)

def convert_result(s):
  m = re.match(r'^([1-9][0-9]+) - ([1-9][0-9]+) \(([012])\)$', s)
  if m is None:
    return None
  return Result(int(m.group(1)), int(m.group(2)), int(m.group(3)))

sqlite3.register_adapter(Result, adapt_result)
sqlite3.register_converter('result', convert_result)

class Predictions(object):
  def __init__(self, conn, players, matches):
    self.conn = conn
    self.players = players
    self.matches = matches
    self.conn.execute('''CREATE TABLE IF NOT EXISTS predictions
                         (player_id text,
                          match_id text,
                          result result,
                          time timestamp)''')
    self.conn.commit()

  def addPrediction(self, player, match, result, time):
    res = self.conn.execute('''SELECT result, time FROM predictions
                               WHERE player_id=? and match_id=?''',
                            (player.id, match.id))
    rows = [r for r in res]
    if len(rows) == 0:
      self.conn.execute('''INSERT INTO predictions
                           (player_id, match_id, result, timestamp)
                           values(?, ?, ?, ?)''',
                        (player.id, match.id, result, time))
    else:
      self.conn.execute('''UPDATE predictions SET result=?, timestamp=?
                           WHERE player_id=?, match_id=?''',
                        (result, time))
    self.conn.commit()

