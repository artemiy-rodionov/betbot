import pytz
import re
import sqlite3
from collections import defaultdict

import dateutil.parser

from .sqlite_context import dbopen
from . import sources

BLANK_FLAG = '\U0001F3F3\uFE0F'
ZWNBSP = '\uFEFF'
CUP = '\U0001F3C6'
BRONZE_MEDAL = '\U0001F949'

MSK_TZ = pytz.timezone('Europe/Moscow')


def iter_matches(matches_info):
    for tour in ['league', 'groups', 'knockout']:
        if tour not in matches_info:
            continue
        for subgroup in matches_info[tour].values():
            for match in subgroup['matches']:
                yield subgroup['name'], match


def sorted_matches(matches_info):
    return sorted(iter_matches(matches_info), key=lambda m: m[1]['name'])


class Database(object):
    def __init__(self, config):
        matches_data = sources.load_fixtures(config)
        self.teams = Teams(matches_data)
        self.matches = Matches(matches_data, self.teams)
        self.players = Players(config['base_file'], config['admin_id'])
        self.predictions = Predictions(config['base_file'], self.players, self.matches)


class Team(object):
    @staticmethod
    def make_real(info):
        return Team(
            info['id'],
            info['name'],
            info['fifaCode'],
            info['emojiString']
        )

    @staticmethod
    def make_fake(id, match_type, label):
        if match_type == 'qualified':
            type, group = label.split('_')
            name = '%s %s' % (type.upper(), group.upper())
            short_name = '%s%s' % (type[0].upper(), group.upper())
        elif match_type in ['winner', 'loser']:
            name = '%s %d' % (match_type.upper(), label)
            short_name = '%s%d' % (match_type[0].upper(), label)
        return Team(id, name, short_name, BLANK_FLAG)

    def __init__(self, id, name, short_name, flag):
        self._id = id
        self._name = name
        self._short_name = short_name
        self._flag = flag

    def id(self):
        return self._id

    def name(self):
        return self._name

    def short_name(self):
        return self._short_name

    def flag(self):
        return self._flag or ''

    def label(self, left_flag=True, short=False):
        name = self.short_name() if short else self.name()
        if left_flag:
            return '%s%s%s' % (self.flag(), ZWNBSP, name)
        else:
            return '%s%s%s' % (name, ZWNBSP, self.flag())

    def __str__(self):
        return (
            '%s: %s <%s> %s' %
            (self.id(),
             self.name(),
             self.short_name(),
             self.flag()))


class Teams(object):
    @staticmethod
    def get_team_id(match_type, team_label):
        if match_type == 'group':
            return team_label
        return '%s_%s' % (match_type, team_label)

    def __init__(self, matches_data):
        self.teams = dict()
        for team_info in matches_data['teams']:
            team = Team.make_real(team_info)
            self.teams[team.id()] = team

        if 'groups' not in matches_data:
            return

        for group, group_info in matches_data['groups'].items():
            w, r = group_info['winner'], group_info['runnerup']
            if w is not None:
                assert(w in self.teams)
                self.teams[Teams.get_team_id(
                    'qualified', 'winner_%s' % group)] = self.teams[w]
            if r is not None:
                assert(r in self.teams)
                self.teams[Teams.get_team_id(
                    'qualified', 'runner_%s' % group)] = self.teams[r]

        for _, match_info in sorted_matches(matches_data):
            match_type = match_info['type']
            match_teams = {}
            for team_type in ['home', 'away']:
                team_label = match_info['%s_team' % team_type]
                id = Teams.get_team_id(match_type, team_label)
                if id not in self.teams:
                    self.teams[id] = Team.make_fake(id, match_type, str(team_label))
                match_teams[team_type] = self.teams[id]
            if match_info['finished'] and match_type != 'group':
                assert(match_info['winner'] in {'home', 'away'})
                win = match_teams[match_info['winner']]
                lose = match_teams['home' if match_info['winner'] == 'away' else 'away']
                self.teams[Teams.get_team_id('winner', match_info['name'])] = win
                self.teams[Teams.get_team_id('loser', match_info['name'])] = lose

    def get_participants(self, match_info):
        return [self.teams[Teams.get_team_id(match_info['type'], match_info[t])]
                for t in ['home_team', 'away_team']]

    def __str__(self):
        return '\n'.join(
            str(v) for v in sorted(
                self.teams.values(),
                key=Team.id))

    def get_team(self, team_id):
        return self.teams[team_id]


class Result(object):
    def __init__(self, goals1, goals2, winner=None):
        self.goals1 = goals1
        self.goals2 = goals2
        if winner is None:
            self.winner = 0 if goals1 == goals2 else (
                1 if goals1 > goals2 else 2)
        else:
            self.winner = winner
        assert((self.goals1 <= self.goals2 or self.winner == 1) and
               (self.goals1 >= self.goals2 or self.winner == 2))

    def goals(self, index):
        return (self.goals1, self.goals2)[index]

    def penalty_win1(self):
        return self.goals1 == self.goals2 and self.winner == 1

    def penalty_win2(self):
        return self.goals1 == self.goals2 and self.winner == 2

    def label(self):
        BALL = u'\u26bd'
        return '%s%d - %d%s' % (BALL if self.penalty_win1() else '', self.goals1,
                                self.goals2, BALL if self.penalty_win2() else '')

    def score(self, prediction):
        p = prediction
        if p is None:
            return 0
        return (int(self.winner == p.winner) +
                int((self.goals1 - self.goals2) == (p.goals1 - p.goals2)) +
                int(self.goals1 == p.goals1 and self.goals2 == p.goals2) +
                int(self.winner != 0 and (self.goals1 == self.goals2) and (p.goals1 == p.goals2)))

    def __str__(self):
        return "%d - %d (%d)" % (self.goals1, self.goals2, self.winner)


def adapt_result(result):
    return str(result)


def convert_result(s):
    if not isinstance(s, str):
        s = s.decode()
    m = re.match(r'^([0-9]) - ([0-9]) \(([012])\)$', s)
    if m is None:
        return None
    return Result(int(m.group(1)), int(m.group(2)), int(m.group(3)))


sqlite3.register_adapter(Result, adapt_result)
sqlite3.register_converter('result', convert_result)


class Match(object):
    SHORT_ROUNDS = {
        'Group A': 'A',
        'Group B': 'B',
        'Group C': 'C',
        'Group D': 'D',
        'Group E': 'E',
        'Group F': 'F',
        'Group G': 'G',
        'Group H': 'H',
        'Round of 16': u'⅛',
        'Quarter-finals': u'¼',
        'Semi-finals': u'½',
        'Third place play-off': BRONZE_MEDAL,
        'Final': CUP
    }

    @staticmethod
    def parse_result(match_info):
        h, a = match_info['home_result'], match_info['away_result']
        if h is None or a is None:
            return None
        if 'winner' not in match_info or match_info['winner'] is None:
            return Result(h, a)
        return Result(h, a, {'home': 1, 'away': 2}[match_info['winner']])

    def __init__(self, round, match_info, teams):
        self._id = match_info['name']
        self._round = round
        self._teams = teams.get_participants(match_info)
        self._start_time = dateutil.parser.parse(
            match_info['date']).astimezone(pytz.utc)
        self._is_playoff = 'home_penalty' in match_info
        self._is_finished = match_info['finished']
        self._result = Match.parse_result(match_info)
        assert(not self._is_finished or self._result is not None)

    def id(self):
        return self._id

    def round(self):
        return self._round

    def short_round(self):
        round = self.round()
        return Match.SHORT_ROUNDS.get(round, round)

    def team(self, index):
        return self._teams[index]

    def start_time(self):
        return self._start_time

    def is_playoff(self):
        return self._is_playoff

    def result(self):
        return self._result

    def is_finished(self):
        return self._is_finished

    def label(self, result=None, short=False):
        t0, t1 = self.team(0), self.team(1)
        return '%s %s %s' % (
            t0.label(left_flag=True, short=short),
            '-' if result is None else result.label(),
            t1.label(left_flag=False, short=short)
        )

    def __str__(self):
        res = '%s (%s) %s - %s (%s)' % (self.id(),
                                        self.round(),
                                        self.team(0).short_name(),
                                        self.team(1).short_name(),
                                        self.start_time())
        if self.is_playoff():
            res += ' P'
        if self.result() is not None:
            res += ' %s' % self.result()
        if self.is_finished():
            res += ' F'
        return res


class Matches(object):
    def __init__(self, matches_data, teams):
        self.matches = dict()
        for round, match_info in iter_matches(matches_data):
            match = Match(round, match_info, teams)
            self.matches[match.id()] = match

    def getMatchesAfter(self, time):
        return sorted(
            [m for m in self.matches.values() if m.start_time() > time],
            key=lambda m: (m.start_time(), not m.is_finished(), m.id())
        )

    def getMatchesBefore(self, time):
        return sorted(
            [m for m in self.matches.values() if m.start_time() <= time],
            key=lambda m: (m.start_time(), not m.is_finished(), m.id())
        )

    def getMatch(self, match_id):
        return self.matches[match_id]

    def __str__(self):
        return '\n'.join(
            str(m) for m in sorted(
                self.matches.values(),
                key=Match.start_time))


class Player(object):
    def __init__(self, id, first_name, last_name, display_name, is_queen):
        self._id = id
        self._first_name = first_name
        self._last_name = last_name
        self._display_name = display_name
        self._is_queen = is_queen

    def id(self):
        return self._id

    def name(self):
        if self._display_name is not None:
            return self._display_name
        if self._first_name and self._last_name:
            return '%s %s' % (self._first_name, self._last_name)
        return self._first_name if self._first_name is not None else \
            self._last_name if self._last_name is not None else \
            '<id: %d>' % self._id

    def short_name(self):
        return self._first_name if self._first_name is not None else \
            self._last_name if self._last_name is not None else \
            self._display_name if self._display_name is not None else \
            '<id: %d>' % self._id

    def is_queen(self):
        return self._is_queen

    def __str__(self):
        return '%s (%d)' % (self.name(), self.id())


class Players(object):
    def __init__(self, db_path, admin_id):
        self.db_path = db_path
        self.admin_id = admin_id
        with self.db() as db:
            db.execute('''CREATE TABLE IF NOT EXISTS players
                    (id integer, first_name text, last_name text, display_name text,
                     is_queen integer not null default 1)''')

    def getPlayer(self, id):
        with self.db() as db:
            res = db.execute(
                '''SELECT first_name, last_name, display_name, is_queen FROM players WHERE id=?''',
                (id,)
            ).fetchone()
        if res is None:
            return None
        return Player(id, res[0], res[1], res[2], bool(res[3]))

    def getAllPlayers(self):
        players = []
        with self.db() as db:
            for row in db.execute(
                '''SELECT first_name, last_name, display_name, is_queen, id FROM players'''
            ):
                players.append(Player(
                    row[4],
                    row[0],
                    row[1],
                    row[2],
                    bool(row[3])
                ))
        return players

    def createPlayer(self, id, first_name, last_name, is_queen=False):
        with self.db() as db:
            db.execute(
                '''INSERT INTO players (id, first_name, last_name, display_name, is_queen)
                    VALUES (?,?,?,?,?)''', (id, first_name, last_name, None, int(is_queen)))
        return self.getPlayer(id)

    def isRegistered(self, id):
        return self.getPlayer(id) is not None

    def isAdmin(self, id):
        return id == self.admin_id

    def changeIsQueen(self, id, is_queen):
        with self.db() as db:
            db.execute(
                '''UPDATE players SET is_queen=? WHERE id=?''', (int(is_queen), id))

    def db(self):
        return dbopen(self.db_path)


class Predictions(object):
    def __init__(self, db_path, players, matches):
        self.db_path = db_path
        self.players = players
        self.matches = matches
        with self.db() as db:
            db.execute('''CREATE TABLE IF NOT EXISTS predictions
                    (player_id integer, match_id integer, result result, time timestamp)''')

    def addPrediction(self, player, match, result, time):
        with self.db() as db:
            res = db.execute(
                'SELECT result, time FROM predictions WHERE player_id=? and match_id=?',
                (player.id(), match.id())
            )
            rows = [r for r in res]
            if len(rows) == 0:
                db.execute(
                    '''
                    INSERT INTO predictions (player_id, match_id, result, time) values(?, ?, ?, ?)
                    ''',
                    (player.id(), match.id(), result, time)
                )
            else:
                db.execute(
                    'UPDATE predictions SET result=?, time=?  WHERE player_id=? AND match_id=?',
                    (result, time, player.id(), match.id())
                )

    def getForPlayer(self, player):
        predictions = []
        with self.db() as db:
            for row in db.execute('''SELECT result, match_id FROM predictions
                               WHERE player_id=?''', (player.id(),)):
                res = row[0]
                match = self.matches.getMatch(row[1])
                predictions.append((match, res))
        predictions.sort(key=lambda p: p[0].start_time())
        return predictions

    def getForMatch(self, match):
        predictions = []
        with self.db() as db:
            for row in db.execute('''SELECT player_id, result FROM predictions
                               WHERE match_id=?''', (match.id,)):
                res = row[1]
                player = self.players.getPlayer(row[0])
                predictions.append((player, res))
        predictions.sort(key=lambda p: p[0].name)
        return predictions

    def genResults(self, now):
        players = self.players.getAllPlayers()
        matches = self.matches.getMatchesBefore(now)
        predictions = defaultdict(lambda: defaultdict(lambda: None))
        with self.db() as db:
            for row in db.execute(
                '''SELECT player_id, match_id, result FROM predictions
                               WHERE match_id IN (%s)''' %
                ','.join(
                    '?' *
                    len(matches)),
                tuple(
                    m.id() for m in matches)):
                predictions[row[0]][row[1]] = row[2]
        results = {
            'matches': [],
            'players': defaultdict(lambda: {'predictions': []})
        }
        for match in matches:
            results['matches'].append({
                'id': match.id(),
                'team0': match.team(0).label(),
                'team1': match.team(1).label(),
                'result': match.result().label() if match.result() is not None else '―',
                'label': match.label(match.result()),
                'round': match.short_round(),
                'time': match.start_time().astimezone(MSK_TZ).strftime('%d.%m %H:%M'),
                'short_label': match.label(None, short=True)
            })
            for player in players:
                p = predictions[int(player.id())][int(match.id())]
                results['players'][player.id()]['predictions'].append({
                    'result': None if p is None else p.label(),
                    'score': None if not match.is_finished() else match.result().score(p)
                })
        for player in players:
            score = sum(0 if s['score'] is None else s['score']
                        for s in results['players'][player.id()]['predictions'])
            results['players'][player.id()]['name'] = player.name()
            results['players'][player.id()]['score'] = score
            results['players'][player.id()]['is_queen'] = player.is_queen()
        return results

    def getMissingPlayers(self, match_id):
        with self.db() as db:
            rows = db.execute('''SELECT id FROM players WHERE id NOT IN
                               (SELECT player_id FROM predictions WHERE match_id = ?)''',
                              (match_id,))
            return [row[0] for row in rows]

    def db(self):
        return dbopen(self.db_path)
