# -*- coding: utf-8 -*-

import csv
import os
import pytz
import sqlite3
from datatime import datatime

def create_csv_reader(iterable):
  return csv.DictReader(filter(lambda row: len(row) > 0 and row[0] != '#',
                               iterable))

class Database(object):
  def __init__(self, db_path, data_dir):
    self.conn = sqlite3.connect(path)
    self.teams = Teams(os.path.join(data_dir, Teams.DATA_FILENAME))
    self.matches = Matches(os.path.join(data_dir, Matches.DATA_FILENAME),
                           self.teams)

def Team(object):
  def __init__(self, id, name, group):
    self.id = id
    self.name = name
    self.group = group

def Teams(object):
  DATA_FILENAME = 'teams.csv'

  def __init__(self, data_path):
    self.teams = dict()
    with open(data_path) as table:
      for row in create_csv_reader(table):
        self.teams[row['id']] = Team(**row)

  def get_team(self, team_id):
    return self.teams[team_id]

class Match(object):
  def __init__(self, id, team1, team2, time):
    self.id = id
    self.team1 = team1
    self.team2 = team2
    self.time = time


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
        time = cest_tz.localize(datetime.strptime(row['time'], '%d %B %Y %H:%M'))
        time = time.astimezone(pytz.utc)
        self.matches[id] = Match(id, team1, team2, time)
        id += 1

