#!/usr/bin/env python

import sys
import argparse
import inspect
import json
import logging

from betbot import bot

logging.basicConfig(
    format= '%(asctime)s (%(filename)s:%(lineno)d %(threadName)s) %(levelname)s: "%(message)s"'
)
logging.getLogger().setLevel(logging.DEBUG)


def date_arg(s):
    try:
        return pytz.utc.localize(datetime.strptime(s, '%Y-%m-%d %H:%M'))
    except ValueError:
        raise argparse.ArgumentTypeError('Not a valid date: %s' % s)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('config')
    parser.add_argument('-d', '--dump', help='Print teams and matches and exit',
                        action='store_true')
    parser.add_argument('-r', '--results', help='Print results json and exit',
                        nargs='?', const=bot.utcnow(), type=date_arg)
    parser.add_argument('--update', help='Update json results and exit', action='store_true')
    args = parser.parse_args(sys.argv[1:])
    with open(args.config) as config_file:
        config = json.load(config_file)
        if args.dump:
            result = bot.dump_results(config, args.results)
        elif args.update:
            result = bot.update_fixtures(config)
        else:
            result = bot.start(config)
        sys.exit(result)
