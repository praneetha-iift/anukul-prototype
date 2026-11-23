"""Anukul 'Sense -> Decide' replay on real data: CU-BEMS (Chulalongkorn Univ., Bangkok office, 2019, 1-min).
Finds AC energy that ran while a zone showed no sign of people, and AC running while the zone was already cold.
Occupancy proxy: lighting + plug load above that zone's own night-time standby level."""
import pandas as pd, numpy as np, json, sys, re
out = {}
for fl in ['2019Floor7.csv', '2019Floor2.csv']:
    df = pd.read_csv(f'/home/claude/anukul/data/cubems/{fl}', parse_dates=['Date']).set_index('Date')
    df = df.resample('15min').mean()
    zones = sorted(set(re.match(r'(z\d+)_', c).group(1) for c in df.columns))
    tot = dict(ac=0, ac_offhours=0, ac_empty=0, ac_cold=0, ac_empty_workhours=0)
    per = {}
    for z in zones:
        ac = [c for c in df.columns if c.startswith(z + '_AC')]
        if not ac:
            continue
        acp = df[ac].sum(axis=1)
        act = df[[c for c in df.columns if c.startswith(z + '_') and ('Light' in c or 'Plug' in c)]].sum(axis=1)
        night = act[(act.index.hour >= 1) & (act.index.hour < 5)]
        standby = night.quantile(0.9)
        occupied = act > standby * 1.5 + 0.05
        tcol = [c for c in df.columns if c.startswith(z + '_') and 'degC' in c]
        temp = df[tcol].mean(axis=1) if tcol else pd.Series(np.nan, index=df.index)
        wk = (df.index.dayofweek < 5) & (df.index.hour >= 8) & (df.index.hour < 18)
        on = acp > 0.2
        kwh = lambda m: float((acp[m]).sum() * 0.25)
        r = dict(ac=kwh(on), ac_offhours=kwh(on & ~wk), ac_empty=kwh(on & ~occupied),
                 ac_empty_workhours=kwh(on & ~occupied & wk),
                 ac_cold=kwh(on & occupied & (temp < 23.0)), standby_kW=float(standby))
        per[z] = r
        for k in tot:
            tot[k] += r[k]
    out[fl] = dict(total=tot, zones=per, days=float((df.index[-1] - df.index[0]).days))
json.dump(out, open('/home/claude/anukul/analysis/cubems_waste.json', 'w'), indent=1)
for fl, d in out.items():
    t = d['total']
    print(fl, f"{d['days']:.0f} days | AC {t['ac']:.0f} kWh | AC while zone empty {t['ac_empty']:.0f} ({100*t['ac_empty']/t['ac']:.1f}%) "
          f"[of which in work hours {t['ac_empty_workhours']:.0f}] | off-hours AC {t['ac_offhours']:.0f} ({100*t['ac_offhours']/t['ac']:.1f}%) | AC while occupied & <23C {t['ac_cold']:.0f} ({100*t['ac_cold']/t['ac']:.1f}%)")

# ---- what Anukul's rules would have saved on these floors (estimate) ----
# R1 'empty zone': AC off when no sign of people for the interval (full kWh of those intervals)
# R2 'overcooling': set point raised toward 24 C (BEE default); saving per degC is an ASSUMPTION
#     taken as 3 %/degC (low) and 6 %/degC (BEE figure), capped at 4 degC of raise.
est = {}
for fl in ['2019Floor7.csv', '2019Floor2.csv']:
    df = pd.read_csv(f'/home/claude/anukul/data/cubems/{fl}', parse_dates=['Date']).set_index('Date').resample('15min').mean()
    zones = sorted(set(re.match(r'(z\d+)_', c).group(1) for c in df.columns))
    tot_ac = r1 = r2lo = r2hi = 0.0
    for z in zones:
        ac = [c for c in df.columns if c.startswith(z + '_AC')]
        if not ac:
            continue
        acp = df[ac].sum(axis=1)
        act = df[[c for c in df.columns if c.startswith(z + '_') and ('Light' in c or 'Plug' in c)]].sum(axis=1)
        standby = act[(act.index.hour >= 1) & (act.index.hour < 5)].quantile(0.9)
        occ = act > standby * 1.5 + 0.05
        tcol = [c for c in df.columns if c.startswith(z + '_') and 'degC' in c]
        T = df[tcol].mean(axis=1) if tcol else pd.Series(np.nan, index=df.index)
        on = acp > 0.2
        e = acp * 0.25
        tot_ac += e[on].sum()
        r1 += e[on & ~occ].sum()
        gap = (24.0 - T).clip(lower=0, upper=4).fillna(0)
        m = on & occ
        r2lo += (e[m] * 0.03 * gap[m]).sum()
        r2hi += (e[m] * 0.06 * gap[m]).sum()
    est[fl] = dict(ac_kwh=tot_ac, empty_kwh=r1, overcool_lo=r2lo, overcool_hi=r2hi,
                   pct_lo=100 * (r1 + r2lo) / tot_ac, pct_hi=100 * (r1 + r2hi) / tot_ac)
    print(fl, {k: round(v, 1) for k, v in est[fl].items()})
json.dump({'waste': out, 'estimate': est}, open('/home/claude/anukul/analysis/cubems_waste.json', 'w'), indent=1)
