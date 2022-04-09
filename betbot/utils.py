import datetime
import inspect

import pytz


def utcnow():
    return pytz.utc.localize(datetime.datetime.utcnow())


def lineno():
    return inspect.currentframe().f_back.f_lineno
