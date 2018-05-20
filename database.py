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
  def __init__(self, id, team1, team2, time, is_playoff):
    self.id = id
    self.team1 = team1
    self.team2 = team2
    self.time = time
    self.is_playoff = is_playoff

  def __str__(self):
    return "%s: %s - %s (%s)" % \
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
        is_playoff = bool(int(row['is_playoff']))
        self.matches[str(id)] = Match(str(id), team1, team2, time, is_playoff)
        id += 1

  def __str__(self):
     return '\n'.join(str(m) for m in self.matches.values())

  def getMatchesAfter(self, time):
    return sorted([m for m in self.matches.values() if m.time > time],
                  key=lambda m: m.time)

  def getMatch(self, match_id):
    return self.matches[match_id] if match_id in self.matches else None


class Player(object):
  def __init__(self, id, first_name, last_name, display_name):
    self._id = id
    self._first_name = first_name
    self._last_name = last_name
    self._display_name = display_name

  def id(self):
    return self._id

  def name(self):
    if self._display_name is not None:
      return self._display_name
    if self._first_name and self._last_name:
      return '%s %s' % (self._first_name, self._last_name)
    return self._first_name if self._first_name is not None else \
           self._last_name if self._last_name is not None else \
           '<UNKNOWN>'

  def short_name(self):
    return self._first_name if self._first_name is not None else \
           self._last_name if self._last_name is not None else \
           self._display_name if self._display_name is not None else \
           '<UNKNOWN>'

  def __str__(self):
    return '%s (%s)' % (self.name(), self.id())

class Players(object):
  def __init__(self, conn):
    self.conn = conn
    self.conn.execute('''CREATE TABLE IF NOT EXISTS players
                         (id text, first_name text, last_name text, display_name text)''')
    self.conn.commit()

  def getPlayer(self, id):
    res = self.conn.execute('''SELECT first_name, last_name, display_name
                               FROM players WHERE id=?''', (id,)).fetchone()
    if res is None:
      return None
    return Player(id, res[0], res[1], res[2])

  def createPlayer(self, id, first_name, last_name):
    self.conn.execute('''INSERT INTO players (id, first_name, last_name, display_name)
                         VALUES (?,?,?,?)''',
                      (id, first_name, last_name, None))
    self.conn.commit()
    return self.getPlayer(id)

  def isRegistered(self, id):
    return self.getPlayer(id) is not None

  def isAdmin(self, id):
    return id == 485651

class Result(object):
  def __init__(self, goals1, goals2, winner=None):
    self.goals1 = goals1
    self.goals2 = goals2
    if winner is None:
      self.winner = 0 if goals1 == goals2 else (1 if goals1 > goals2 else 2)
    else:
      self.winner = winner

  def penalty_win1(self):
    return self.goals1 == self.goals2 and self.winner == 1

  def penalty_win2(self):
    return self.goals1 == self.goals2 and self.winner == 2

def adapt_result(result):
  return "%d - %d (%d)" % (result.goals1, result.goals2, result.winner)

def convert_result(s):
  m = re.match(r'^([0-9]) - ([0-9]) \(([012])\)$', s)
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
                            (player.id(), match.id))
    rows = [r for r in res]
    if len(rows) == 0:
      self.conn.execute('''INSERT INTO predictions
                           (player_id, match_id, result, time)
                           values(?, ?, ?, ?)''',
                        (player.id(), match.id, result, time))
    else:
      self.conn.execute('''UPDATE predictions SET result=?, time=?
                           WHERE player_id=? AND match_id=?''',
                        (result, time, player.id(), match.id))
    self.conn.commit()

  def getForPlayer(self, player):
    predictions = []
    for row in self.conn.execute('''SELECT result, match_id FROM predictions
                                    WHERE player_id=?''', (player.id(),)):
      res = row[0]
      match = self.matches.getMatch(row[1])
      predictions.append((match, res))
    predictions.sort(key=lambda p: p[0].time)
    return predictions

  def getForMatch(self, match):
    predictions = []
    for row in self.conn.execute('''SELECT player_id, result FROM predictions
                                    WHERE match_id=?''', (match.id,)):
      res = row[1]
      player = self.players.getOrCreatePlayer(row[0])
      predictions.append((player, res))
    predictions.sort(key=lambda p: p[0].name)
    return predictions


