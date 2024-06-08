"""
Make sure to install packages: bar-chart-race(requires ffmpeg), pandas
"""

import datetime
from collections import defaultdict
import bar_chart_race as bcr
import pandas as pd
import json

from config import config
from betbot import conf


def parse_dts(val):
    curyear = datetime.datetime.utcnow().year
    dt = datetime.datetime.strptime(val, '%d.%m %H:%M')
    dt = dt.replace(year=curyear)
    now = datetime.datetime.now()
    if dt > now:
        dt = dt.replace(year=curyear-1)
    return dt


def build_chart_race():
    results_fpath = conf.get_results_file(config)
    with open(results_fpath) as fp:
        results = json.load(fp)

    scores = results['players']
    ms = {m['id']: m for m in results['matches']}

    res = defaultdict(list)
    sc = [s for s in scores.values()]
    for m in ms.values():
        m['dt'] = parse_dts(m['time'])

    for m in sorted(ms.values(), key=lambda m: m['dt']):
        mid = m['id']
        for pl in sc:
            for pr in pl['predictions']:
                if pr['match_id'] == mid:
                    try:
                        curscore = res[pl['name']][-1]
                    except IndexError:
                        curscore = 0
                    pr_score = pr['score'] or 0
                    res[pl['name']].append(curscore + pr_score)
                    break
    df = pd.DataFrame.from_dict(res)
    chart_race_fpath = conf.get_chart_race_file(config)
    gr = bcr.bar_chart_race(
        df,
        filename=chart_race_fpath,
        # steps_per_period=10,
        interpolate_period=True,
        period_length=400,
        period_fmt='Номер матча - {x:.0f}',
    )
    return gr
