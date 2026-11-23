"""Controllers for the BOPTEST multizone_office_simple_air test case.

baseline : no overrides -> BOPTEST's embedded rule-based control (fixed schedule,
           fixed 24 C cooling set point, fixed design minimum outdoor air).
anukul   : the Anukul decision layer (Sense -> Decide -> Act), see AnukulController.
"""
ZONES = ['cor', 'eas', 'nor', 'sou', 'wes']
ZN = {'cor': 'Cor', 'eas': 'Eas', 'nor': 'Nor', 'sou': 'Sou', 'wes': 'Wes'}


class Baseline:
    forecast_points = []
    horizon = 0

    def compute(self, y, fc):
        return {}

    def log_row(self, y, u):
        from anukul_controller import AnukulController
        return AnukulController.log_row(self, y, u)


def make(name):
    if name == 'baseline':
        return Baseline()
    if name.startswith('anukul'):
        from anukul_controller import AnukulController
        return AnukulController(name.split(':', 1)[1] if ':' in name else None)
    raise ValueError(name)
