"""KPI table (CSV + markdown) and a summary chart from app_data.json."""
import json, csv
import matplotlib; matplotlib.use('Agg')
import matplotlib.pyplot as plt
D = json.load(open('/home/claude/anukul/app/app_data.json'))
LAB = {'peak_heat_day':'Peak winter','typical_heat_day':'Typical winter','mix_day':'Spring/autumn','typical_cool_day':'Typical summer','peak_cool_day':'Peak summer',
       'delhi_winter':'Winter (Jan)','delhi_spring':'Spring (Mar)','delhi_monsoon':'Monsoon (Aug)','delhi_peak_cool':'Peak summer (May)'}
ORDER = list(LAB)
by = {}
for r in D['kpis']:
    by.setdefault((r['city'], r['scenario']), {})[r['mode']] = r
rows = []
for (city, sc), m in sorted(by.items(), key=lambda kv: (kv[0][0], ORDER.index(kv[0][1]))):
    b = m.get('baseline')
    if not b: continue
    for md in ['eco', 'comfort']:
        a = m.get(md)
        if not a: continue
        rows.append(dict(city=city.split(' (')[0], period=LAB[sc], mode=md,
            energy_base=round(b['ener'],3), energy=round(a['ener'],3), energy_pct=round(100*(a['ener']-b['ener'])/b['ener'],1),
            tdis_base=round(b['tdis'],2), tdis=round(a['tdis'],2), tdis_pct=round(100*(a['tdis']-b['tdis'])/b['tdis'],1) if b['tdis'] else None,
            idis_base=round(b['idis'],1), idis=round(a['idis'],1)))
with open('/home/claude/anukul/repo/results/kpis.csv','w',newline='') as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)
for r in rows: print(r)
# chart: energy % and thermal % for comfort mode, per city
plt.rcParams.update({'font.family':'serif','font.serif':['Times New Roman','DejaVu Serif'],'font.size':11})
cities = sorted(set(r['city'] for r in rows))
fig, axes = plt.subplots(1, len(cities), figsize=(6.2*len(cities), 3.8), squeeze=False)
for ax, c in zip(axes[0], cities):
    rr = [r for r in rows if r['city']==c and r['mode']=='comfort']
    y = range(len(rr))
    ax.barh([i+0.2 for i in y], [r['energy_pct'] for r in rr], height=0.38, color='#0b3d2e', label='HVAC energy')
    ax.barh([i-0.2 for i in y], [r['tdis_pct'] for r in rr], height=0.38, color='#3dcd58', label='Thermal discomfort')
    for i, r in zip(y, rr):
        ax.text(r['energy_pct'] + (1 if r['energy_pct']>=0 else -1), i+0.2, f"{r['energy_pct']:+.0f}%", va='center', ha='left' if r['energy_pct']>=0 else 'right', fontsize=9)
        ax.text(r['tdis_pct'] + (1 if r['tdis_pct']>=0 else -1), i-0.2, f"{r['tdis_pct']:+.0f}%", va='center', ha='left' if r['tdis_pct']>=0 else 'right', fontsize=9)
    ax.set_yticks(list(y)); ax.set_yticklabels([r['period'] for r in rr]); ax.axvline(0, color='#555', lw=0.8)
    ax.set_xlim(-100, 40); ax.set_title(f'{c}: Anukul Comfort vs normal controls', loc='left', fontsize=12, color='#0b3d2e')
    ax.set_xlabel('change vs normal controls (%)')
    for s in ['top','right']: ax.spines[s].set_visible(False)
fig.legend(*axes[0][0].get_legend_handles_labels(), loc='upper right', ncol=2, frameon=False, fontsize=10)
fig.text(0.01, 0.01, 'Source: BOPTEST multizone_office_simple_air, KPIs from BOPTEST calculator. CO₂ violations (ppm-h) shown in kpis.csv.', fontsize=8, color='#555')
fig.tight_layout(rect=(0,0.04,1,0.92)); fig.savefig('/home/claude/anukul/repo/results/results_chart.png', dpi=200)
