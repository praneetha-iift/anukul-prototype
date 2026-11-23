import json,glob,sys
for f in sorted(glob.glob(sys.argv[1]+'/*.json')):
    d=json.load(open(f)); k=d['kpis']; tr=d['trace']
    E=lambda key: sum(r.get(key,0) for r in tr)*900/3.6e6
    print(f"{d["scenario"]:18s} {d["controller"]:22s} ener {k['ener_tot']:.4f} tdis {k['tdis_tot']:6.2f} idis {k['idis_tot']:8.1f} cost {k['cost_tot']:.4f} | chi {E('Pchi'):6.0f} fan {E('Pfan'):6.0f} hea {E('Phea'):6.0f} kWh")
