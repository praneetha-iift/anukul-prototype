"""Collect BOPTEST results + CU-BEMS findings into one compact JSON for the FM app and the report."""
import json, glob, os, sys
S = '/tmp/claude-0/-home-claude/3b8a3c7c-851e-576a-a58f-345099039202/scratchpad'
MODE = {'baseline': 'baseline', 'anukul:night,dcv,sat': 'eco', 'anukul': 'comfort'}
CITY = {'full': 'Chicago (BOPTEST standard)', 'delhi7': 'New Delhi (ISHRAE weather)'}
out = {'kpis': [], 'replay': {}, 'area_m2': 1662.66}
runs = {}
for d in ['full', 'delhi7']:
    for f in sorted(glob.glob(f'{S}/{d}/*.json')):
        r = json.load(open(f)); m = MODE.get(r['controller'])
        if not m: continue
        runs[(d, r['scenario'], m)] = r
        k = r['kpis']; tr = r['trace']
        E = lambda key: round(sum(x.get(key, 0) for x in tr) * 900 / 3.6e6, 1)
        out['kpis'].append(dict(city=CITY[d], scenario=r['scenario'], mode=m, ener=k['ener_tot'], tdis=k['tdis_tot'],
                                idis=k['idis_tot'], cost=k['cost_tot'], emis=k['emis_tot'], pele=k['pele_tot'],
                                kwh_chiller=E('Pchi'), kwh_fan=E('Pfan'), kwh_heat=E('Phea'),
                                n_decisions=len(r.get('decisions', [])), days=round(len(tr) / 96, 1)))
def replay(d, scen, day):
    key = f'{d}:{scen}'
    b, c = runs.get((d, scen, 'baseline')), runs.get((d, scen, 'comfort'))
    if not (b and c): return
    t0 = b['trace'][0]['t'] - 900 + day * 86400
    sl = lambda r: [x for x in r['trace'] if t0 < x['t'] <= t0 + 86400]
    pack = lambda rows: dict(T={z: [round(x['T'][z], 2) for x in rows] for z in rows[0]['T']},
                             CO2={z: [round(x['CO2'][z]) for x in rows] for z in rows[0]['CO2']},
                             P=[round(x['P'] / 1000, 2) for x in rows], TOut=[round(x['TOut'], 1) for x in rows])
    dec = [dict(h=round((x['t'] - t0) / 3600, 2), lever=x['lever'], text=x['text'])
           for x in c.get('decisions', []) if t0 < x['t'] <= t0 + 86400]
    out['replay'][key] = dict(city=CITY[d], scenario=scen, day=day, baseline=pack(sl(b)), anukul=pack(sl(c)), decisions=dec)
replay('full', 'typical_cool_day', 6)
replay('delhi7', 'delhi_spring', 5)
replay('delhi7', 'delhi_peak_cool', 3)
replay('full', 'mix_day', 6)
cb = json.load(open('/home/claude/anukul/analysis/cubems_waste.json'))
out['cubems'] = cb
json.dump(out, open('/home/claude/anukul/app/app_data.json', 'w'))
print(len(out['kpis']), 'kpi rows; replays', list(out['replay']))
