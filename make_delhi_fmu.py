"""Build a Delhi-climate copy of the BOPTEST multizone_office_simple_air FMU.
Swaps the Chicago TMY3 weather for ISHRAE-2014 New Delhi (Safdarjung) weather (EPW -> Modelica .mos),
rebuilds the forecast weather.csv, and defines Delhi test periods in days.json.
Building, HVAC sizing and controls are untouched (it is still a Chicago-sized system)."""
import zipfile, json, sys, io, numpy as np, pandas as pd, shutil, os
SRC = '/home/claude/ext/project1-boptest/testcases/multizone_office_simple_air'
DST = '/home/claude/ext/project1-boptest/testcases/multizone_office_simple_air_delhi'
EPW = sys.argv[1]
lines = open(EPW, encoding='latin-1').read().splitlines()
head, data = lines[:8], [l.split(',') for l in lines[8:] if l.strip()]
assert len(data) == 8760, len(data)
# .mos: time + EPW fields 7..35 (29 columns)
mos = ['#1', 'double tab1(8760,30)'] + ['#' + h for h in head]
for i, r in enumerate(data):
    mos.append('\t'.join([f'{i*3600.0:.1f}'] + r[6:35]))
mos = '\n'.join(mos) + '\n'
ep = pd.DataFrame([[float(x) for x in r[6:35]] for r in data])
TDry, TDew, RH, P = ep[0] + 273.15, ep[1] + 273.15, ep[2] / 100, ep[3]
GHI, DNI, DHI = ep[7], ep[8], ep[9]
wd, ws, ntot, nopa, ceil, hir = ep[14] * np.pi / 180, ep[15], ep[16] / 10, ep[17] / 10, ep[19], ep[6]
t_ep = np.arange(8760) * 3600.0

shutil.rmtree(DST, ignore_errors=True)
shutil.copytree(SRC, DST)
zin = zipfile.ZipFile(f'{SRC}/models/wrapped.fmu')
wc = pd.read_csv(io.BytesIO(zin.read('resources/weather.csv')))
tt = wc['time'].values % (365 * 86400)
interp = lambda s: np.interp(tt, t_ep, s.values, period=365 * 86400)
wc['TDryBul'] = interp(TDry); wc['TDewPoi'] = interp(TDew); wc['relHum'] = interp(RH); wc['pAtm'] = interp(P)
wc['HGloHor'] = interp(GHI); wc['HDirNor'] = interp(DNI); wc['HDifHor'] = interp(DHI)
wc['winSpe'] = interp(ws); wc['nTot'] = interp(ntot); wc['nOpa'] = interp(nopa); wc['HHorIR'] = interp(hir)
# wet bulb: Stull (2011) approximation
Tc, rh = wc['TDryBul'] - 273.15, wc['relHum'] * 100
wc['TWetBul'] = 273.15 + Tc * np.arctan(0.151977 * (rh + 8.313659) ** 0.5) + np.arctan(Tc + rh) - np.arctan(rh - 1.676331) \
    + 0.00391838 * rh ** 1.5 * np.arctan(0.023101 * rh) - 4.686035
wc['lat'] = 28.58 * np.pi / 180; wc['lon'] = 77.2 * np.pi / 180
# Delhi test periods (day-of-year of the centre of a 14-day window)
daily = pd.Series(ep[0].values).groupby(np.arange(8760) // 24).mean()
wk = daily.rolling(7, center=True).mean()
days = {'delhi_peak_cool': int(wk.idxmax()), 'delhi_monsoon': 227, 'delhi_spring': 75,
        'delhi_winter': int(wk[:90].idxmin())}
print('Delhi periods', days, {k: round(float(wk[v]), 1) for k, v in days.items()})
zout = zipfile.ZipFile(f'{DST}/models/wrapped.fmu', 'w', zipfile.ZIP_DEFLATED)
for item in zin.infolist():
    b = zin.read(item.filename)
    if item.filename.endswith('.mos'):
        b = mos.encode()
    elif item.filename == 'resources/weather.csv':
        b = wc.to_csv(index=False).encode()
    elif item.filename == 'resources/days.json':
        b = json.dumps(days).encode()
    zout.writestr(item, b)
zout.close()
json.dump(days, open(f'{DST}/models/days.json', 'w'))
print('wrote', DST)
