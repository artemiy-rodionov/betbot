#!/usr/bin/env python

import sys
import datetime
import argparse
import logging

import pytz

from betbot import bot, utils, commands

logging.basicConfig(
    format='%(asctime)s (%(filename)s:%(lineno)d %(threadName)s) %(levelname)s: "%(message)s"'
)
logging.getLogger().setLevel(logging.INFO)


def date_arg(s):
    try:
        return pytz.utc.localize(datetime.strptime(s, "%Y-%m-%d %H:%M"))
    except ValueError:
        raise argparse.ArgumentTypeError("Not a valid date: %s" % s)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "-d", "--dump", help="Print teams and matches and exit", action="store_true"
    )
    parser.add_argument(
        "-r",
        "--results",
        help="Print results json and exit",
        nargs="?",
        const=utils.utcnow(),
        type=date_arg,
    )
    parser.add_argument(
        "--update", help="Update json results and exit", action="store_true"
    )
    parser.add_argument(
        "--update-standings", help="Update standings and exit", action="store_true"
    )
    parser.add_argument(
        "--chart-race", help="Build chart race file and exit", action="store_true"
    )
    args = parser.parse_args(sys.argv[1:])
    if args.results:
        result = commands.dump_results(args.results)
    elif args.dump:
        result = commands.dump_info()
    elif args.update:
        result = commands.update_fixtures()
    elif args.update_standings:
        result = commands.update_standings()
    elif args.chart_race:
        import chart_race

        chart_race.build_chart_race()
        result = 0
    else:
        result = bot.start()
    sys.exit(result)
