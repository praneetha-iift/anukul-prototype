"""Anukul decision layer for the BOPTEST multizone_office_simple_air test case.

Sense -> Decide -> Act, every control step (15 min):

  SENSE   zone temperatures, zone CO2, outdoor / return air temperature,
          plus the occupancy and outdoor-temperature forecast for the next 12 hours.
  DECIDE  four plain rules, each one switchable so its effect can be measured alone:
            guard : keep zones a small margin inside the 20-24 C comfort band
                    (heating 20.2 C, cooling 23.8 C) while the building is occupied
            sat   : supply-air temperature reset (ASHRAE Guideline 36 style "trim & respond");
                    raise supply air from 12 C (max 16 C) when no zone is asking for cooling,
                    lower it as soon as zones ask; hold it while CO2 is high
            dcv   : demand-controlled ventilation; on hot hours (outdoor > return air + 1 C)
                    outdoor air follows the occupancy forecast + measured CO2 (target 750 ppm);
                    at any hour an IAQ guard opens outdoor air when CO2 passes 750 ppm
            night : pre-occupancy flush 02:00-06:00 - only if a hot day is forecast (> 24 C),
                    outdoor air is 3 C cooler than the warmest zone, and no zone is below 21 C
  ACT     writes the BOPTEST override points (the same kind of points a BACnet gateway writes);
          every override not used in a step is explicitly released back to the BMS.
  EXPLAIN every decision is logged in plain English for the facility-manager app.

Modes used in the results:  Eco = night,dcv,sat    Comfort = all four (adds guard).
Levers are chosen with the ANUKUL_LEVERS env var or 'anukul:<levers>' (default: all four).
"""
import os

ZONES = ['cor', 'eas', 'nor', 'sou', 'wes']
ZN = {'cor': 'Cor', 'eas': 'Eas', 'nor': 'Nor', 'sou': 'Sou', 'wes': 'Wes'}
K = 273.15


class AnukulController:
    horizon = 12 * 3600
    ALL_OVERRIDES = ([f'hvac_oveZonSup{ZN[z]}_TZon{m}Set' for z in ZONES for m in ('Hea', 'Coo')] +
                     [f'hvac_oveAhu_{p}' for p in ('TSupSet', 'yOA', 'yFan', 'yRet', 'yCoo', 'yHea')])

    def __init__(self, levers=None):
        lv = levers or os.environ.get('ANUKUL_LEVERS', 'guard,sat,dcv,night')
        self.levers = set(x.strip() for x in lv.split(',') if x.strip())
        self.forecast_points = [f'Occupancy[{z}]' for z in ZONES] + ['TDryBul']
        # comfort-guard set points (C)
        self.heat_occ = float(os.environ.get('ANUKUL_HEAT', 20.2))
        self.cool_occ = float(os.environ.get('ANUKUL_COOL', 23.8))
        # supply-air reset state (C)
        self.sat = 12.0
        self.sat_min, self.sat_max = 12.0, 16.0
        # ventilation
        self.co2_target = float(os.environ.get('ANUKUL_CO2', 750))  # ppm; test-case limit is 894
        self.yoa = 0.32
        self.yoa_min = 0.12
        self.log = []

    # ------------------------------------------------------------------ helpers
    @staticmethod
    def _occupied(tod):
        return 6 * 3600 <= tod < 19 * 3600

    def _say(self, t, lever, text):
        self.log.append({'t': t, 'lever': lever, 'text': text})

    # ------------------------------------------------------------------ main loop
    def compute(self, y, fc):
        t = y['time']
        tod = t % 86400
        occ = self._occupied(tod)
        TZ = {z: y[f'hvac_reaZon{ZN[z]}_TZon_y'] - K for z in ZONES}
        CO2 = {z: y[f'hvac_reaZon{ZN[z]}_CO2Zon_y'] for z in ZONES}
        TOut = y['weaSta_reaWeaTDryBul_y'] - K
        TRet = y['hvac_reaAhu_TRet_y'] - K
        people = sum(fc[f'Occupancy[{z}]'][0] for z in ZONES) if fc else None
        u = {}
        self.last_decisions = []

        # ---- guard: stay inside the comfort band with margin
        if 'guard' in self.levers and occ:
            for z in ZONES:
                u[f'hvac_oveZonSup{ZN[z]}_TZonHeaSet_u'] = self.heat_occ + K
                u[f'hvac_oveZonSup{ZN[z]}_TZonHeaSet_activate'] = 1
                u[f'hvac_oveZonSup{ZN[z]}_TZonCooSet_u'] = self.cool_occ + K
                u[f'hvac_oveZonSup{ZN[z]}_TZonCooSet_activate'] = 1
            hot = [z for z in ZONES if TZ[z] > 23.8]
            if hot:
                self._say(t, 'guard', f"{', '.join(hot)} close to 24 C - holding cooling set point at {self.cool_occ} C")

        # ---- sat: trim & respond supply-air reset
        if 'sat' in self.levers and occ:
            csp = self.cool_occ if 'guard' in self.levers else 24.0
            requests = sum(1 for z in ZONES if TZ[z] > csp - 0.2)
            hi = self.sat_max if TOut < 18 else (self.sat_max - (TOut - 18) * 0.5)
            hi = max(self.sat_min, min(self.sat_max, hi))
            old = self.sat
            if getattr(self, 'iaq_latch', False) and requests == 0:
                requests = -1   # hold supply air: CO2 is high, keep airflow up
            if requests >= 2:
                self.sat -= 0.5 * (requests - 1)
            elif requests == 0:
                self.sat += 0.3
            self.sat = max(self.sat_min, min(hi, self.sat))
            u['hvac_oveAhu_TSupSet_u'] = self.sat + K
            u['hvac_oveAhu_TSupSet_activate'] = 1
            if abs(self.sat - old) >= 0.3:
                self._say(t, 'sat', f"{requests} zone(s) asking for cooling - supply air {old:.1f} -> {self.sat:.1f} C")
        elif not occ:
            self.sat = 12.0

        # ---- dcv: CO2-led outdoor air, only when the economizer is clearly off (hot outside)
        cmax = max(CO2.values())
        # IAQ guard latches on when CO2 nears the target, off once it is well below
        if cmax > self.co2_target:
            self.iaq_latch = True
        elif cmax < self.co2_target - 120:
            self.iaq_latch = False
        hot = TOut > TRet + 1.0
        if 'dcv' in self.levers and occ and (hot or getattr(self, 'iaq_latch', False)):
            # feed-forward from the occupancy forecast + proportional CO2 correction
            ff = 0.12 + 0.25 * (people / 81.0 if people is not None else 1.0)
            self.yoa_i = getattr(self, 'yoa_i', 0.0) + 0.0002 * (cmax - self.co2_target)
            self.yoa_i = max(-0.1, min(0.3, self.yoa_i))
            self.yoa = max(self.yoa_min, min(0.6, ff + 0.002 * (cmax - self.co2_target) + self.yoa_i))
            u['hvac_oveAhu_yOA_u'] = self.yoa
            u['hvac_oveAhu_yOA_activate'] = 1
            if not hot:
                self._say(t, 'dcv', f"IAQ guard on: peak CO2 {cmax:.0f} ppm (target {self.co2_target:.0f}) - outdoor-air damper {self.yoa:.2f}")
            else:
                self._say(t, 'dcv', f"peak CO2 {cmax:.0f} ppm, ~{people:.0f} people forecast - outdoor-air damper {self.yoa:.2f}"
                      if people is not None else f"peak CO2 {cmax:.0f} ppm - outdoor-air damper {self.yoa:.2f}")
        else:
            self.yoa = 0.32
            self.yoa_i = 0.0

        # ---- night: pre-occupancy free-cooling flush (04:00-06:00)
        if 'night' in self.levers and 2 * 3600 <= tod < 6 * 3600:
            tmax = max(TZ.values())
            day_peak = max(fc['TDryBul']) - K if fc else 30.0   # forecast outdoor peak, next 12 h
            if TOut < tmax - 3 and tmax > 22.5 and min(TZ.values()) > 21.0 and day_peak > 24.0:
                u['hvac_oveAhu_yFan_u'] = 0.5
                u['hvac_oveAhu_yFan_activate'] = 1
                u['hvac_oveAhu_yOA_u'] = 1.0
                u['hvac_oveAhu_yOA_activate'] = 1
                u['hvac_oveAhu_yRet_u'] = 0.0
                u['hvac_oveAhu_yRet_activate'] = 1
                u['hvac_oveAhu_yCoo_u'] = 0.0
                u['hvac_oveAhu_yCoo_activate'] = 1
                u['hvac_oveAhu_yHea_u'] = 0.0
                u['hvac_oveAhu_yHea_activate'] = 1
                self._say(t, 'night', f"outdoor {TOut:.1f} C, warmest zone {tmax:.1f} C - hot day ahead (peak {day_peak:.0f} C), flushing with outdoor air before 06:00 (free pre-cooling)")
        # release every override this step did not use (BOPTEST keeps the last value otherwise)
        for k in self.ALL_OVERRIDES:
            u.setdefault(k + '_activate', 0)
        return u

    def log_row(self, y, u):
        return {'t': y['time'],
                'T': {z: y[f'hvac_reaZon{ZN[z]}_TZon_y'] - K for z in ZONES},
                'CO2': {z: y[f'hvac_reaZon{ZN[z]}_CO2Zon_y'] for z in ZONES},
                'P': y['chi_reaPChi_y'] + y['hvac_reaAhu_PFanSup_y'] + y['heaPum_reaPHeaPum_y'] + y['chi_reaPPumDis_y'] + y['heaPum_reaPPumDis_y'],
                'Pchi': y['chi_reaPChi_y'], 'Pfan': y['hvac_reaAhu_PFanSup_y'], 'Phea': y['heaPum_reaPHeaPum_y'],
                'TOut': y['weaSta_reaWeaTDryBul_y'] - K, 'TSup': y['hvac_reaAhu_TSup_y'] - K,
                'u': {k: v for k, v in u.items() if not k.endswith('_activate') and u.get(k[:-2] + '_activate') == 1}}
