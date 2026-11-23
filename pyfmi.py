"""Minimal pyfmi-compatible shim built on FMPy, so the official BOPTEST TestCase
class can run without Docker/pyfmi. Supports FMI 2.0 Co-Simulation FMUs."""
import numpy as np
from collections import OrderedDict
from fmpy import read_model_description, extract
from fmpy.fmi2 import FMU2Slave

_CAUS = {2: 'input', 3: 'output'}


class _FMU:
    def __init__(self, path):
        self.path = path
        self.md = read_model_description(path, validate=False)
        self.unzip = extract(path)
        self.vars = {v.name: v for v in self.md.modelVariables}
        self.slave = FMU2Slave(guid=self.md.guid, unzipDirectory=self.unzip,
                               modelIdentifier=self.md.coSimulation.modelIdentifier,
                               instanceName='boptest')
        self.slave.instantiate()
        self.initialized = False

    def set_log_level(self, *a):
        pass

    def get_version(self):
        return '2.0'

    def get_model_variables(self, causality=None, **kw):
        c = _CAUS.get(causality)
        return OrderedDict((v.name, v) for v in self.md.modelVariables
                           if c is None or v.causality == c)

    def simulate_options(self):
        return {'initialize': True, 'ncp': 500, 'filter': None, 'CVode_options': {}}

    def _attr(self, v, a):
        x = getattr(v, a, None)
        if x is None and v.declaredType is not None:
            x = getattr(v.declaredType, a, None)
        return x

    def get_variable_description(self, n):
        return self.vars[n].description

    def get_variable_unit(self, n):
        u = self._attr(self.vars[n], 'unit')
        if u is None:
            raise Exception('no unit for ' + n)
        return u

    def get_variable_min(self, n):
        m = self._attr(self.vars[n], 'min')
        return float(m) if m is not None else None

    def get_variable_max(self, n):
        m = self._attr(self.vars[n], 'max')
        return float(m) if m is not None else None

    def reset(self):
        if self.initialized:
            self.slave.reset()
        self.initialized = False

    def _get(self, names):
        out = {}
        groups = {'Real': [], 'Integer': [], 'Enumeration': [], 'Boolean': []}
        for n in names:
            groups.setdefault(self.vars[n].type, []).append(n)
        if groups['Real']:
            vals = self.slave.getReal([self.vars[n].valueReference for n in groups['Real']])
            out.update(zip(groups['Real'], vals))
        ints = groups['Integer'] + groups['Enumeration']
        if ints:
            vals = self.slave.getInteger([self.vars[n].valueReference for n in ints])
            out.update(zip(ints, vals))
        if groups['Boolean']:
            vals = self.slave.getBoolean([self.vars[n].valueReference for n in groups['Boolean']])
            out.update((n, float(x)) for n, x in zip(groups['Boolean'], vals))
        return out

    def _set(self, names, vals):
        for n, x in zip(names, vals):
            v = self.vars[n]
            if v.type == 'Real':
                self.slave.setReal([v.valueReference], [float(x)])
            elif v.type == 'Boolean':
                self.slave.setBoolean([v.valueReference], [bool(round(float(x)))])
            else:
                self.slave.setInteger([v.valueReference], [int(round(float(x)))])

    def _apply_input(self, inp):
        if inp is not None:
            row = np.atleast_2d(inp[1])[0]
            self._set(inp[0], row[1:])

    def simulate(self, start_time=0.0, final_time=1.0, options=None, input=None):
        options = options or self.simulate_options()
        names = options.get('filter') or [n for n, v in self.vars.items()
                                          if v.causality in ('input', 'output')]
        if options.get('initialize', True) or not self.initialized:
            if self.initialized:
                self.slave.reset()
            self.slave.setupExperiment(startTime=start_time)
            self.slave.enterInitializationMode()
            self._apply_input(input)
            self.slave.exitInitializationMode()
            self.initialized = True
        ncp = max(1, int(options.get('ncp', 500)))
        if final_time > start_time:
            times = np.linspace(start_time, final_time, ncp + 1)
        else:
            times = np.array([start_time])
        res = {n: [] for n in names}
        res['time'] = []

        def rec(tt):
            vals = self._get(names)
            for n in names:
                res[n].append(vals[n])
            res['time'].append(tt)

        self._apply_input(input)
        rec(times[0])
        for i in range(1, len(times)):
            self._apply_input(input)
            self.slave.doStep(currentCommunicationPoint=times[i - 1],
                              communicationStepSize=times[i] - times[i - 1])
            rec(times[i])
        return {k: np.array(v) for k, v in res.items()}


def load_fmu(path, *a, **kw):
    return _FMU(path)
