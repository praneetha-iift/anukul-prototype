"""Run a BOPTEST scenario locally (no Docker) with a given controller and return KPIs.

Usage: python runner.py <scenario> <controller: baseline|anukul> [out.json]
"""
import sys, os, json, time
HERE = os.path.dirname(os.path.abspath(__file__))
BOPTEST = os.environ.get('BOPTEST_DIR', '/home/claude/ext/project1-boptest')
sys.path.insert(0, HERE)
sys.path.insert(1, BOPTEST)
os.chdir(BOPTEST)
from testcase import TestCase  # noqa: E402

TESTCASE = os.environ.get('BOPTEST_CASE', 'multizone_office_simple_air')
STEP = int(os.environ.get('CONTROL_STEP', '900'))


def run(scenario, controller, fmupath=None, max_steps=None, log_every=96):
    fmupath = fmupath or f'testcases/{TESTCASE}/models/wrapped.fmu'
    tc = TestCase(fmupath=fmupath)
    tc.set_step(STEP)
    status, msg, y = tc.set_scenario({'time_period': scenario, 'electricity_price': 'constant',
                                      'temperature_uncertainty': None, 'solar_uncertainty': None, 'seed': None})
    if status != 200:
        raise RuntimeError(msg)
    print('scenario start day', tc.start_time / 86400, flush=True)
    t0 = time.time()
    u = {}
    k = 0
    trace = []
    while True:
        status, msg, y = tc.advance(u)
        if status != 200 or not isinstance(y, dict) or not y:
            if status != 200:
                print('simulation stopped:', status, str(msg)[:200], flush=True)
            break
        fc = tc.get_forecast(point_names=controller.forecast_points, horizon=controller.horizon, interval=STEP)[2] if controller.forecast_points else {}
        u = controller.compute(y, fc)
        trace.append(controller.log_row(y, u))
        k += 1
        if k % log_every == 0:
            print(f'  step {k} sim-day {y["time"]/86400:.2f} wall {time.time()-t0:.0f}s', flush=True)
        if max_steps and k >= max_steps:
            break
    kpis = tc.get_kpis()[2]
    return kpis, trace, time.time() - t0


if __name__ == '__main__':
    from controllers import make
    scen, name = sys.argv[1], sys.argv[2]
    out = sys.argv[3] if len(sys.argv) > 3 else None
    ms = int(os.environ['MAX_STEPS']) if os.environ.get('MAX_STEPS') else None
    ctl = make(name)
    kpis, trace, wall = run(scen, ctl, max_steps=ms)
    print(json.dumps(kpis, indent=1))
    print('wall seconds', round(wall))
    if out:
        json.dump({'scenario': scen, 'controller': name, 'kpis': kpis, 'trace': trace, 'wall_s': wall, 'decisions': getattr(ctl, 'log', [])}, open(out, 'w'))
