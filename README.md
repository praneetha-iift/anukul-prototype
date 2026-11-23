# Anukul — retrofit the intelligence, not the building

Anukul is a decision layer that sits on top of an office building's existing HVAC controls.
Every 15 minutes it **senses** (zone temperature, CO₂, occupancy, weather forecast),
**decides** with four transparent rules, **acts** by writing set points through the building's
own control points (BACnet), and **verifies** the result against the building's normal behaviour.
Every action comes with a plain-English reason a facility manager can approve, schedule or dismiss.

This repository holds the working prototype for the Schneider Electric Yuva Yodha Energy Tech
Hackathon (Challenge 02, Smart Buildings).

## What is in here

| Folder | What it does |
|---|---|
| `boptest/` | The Anukul controller and a local runner for **BOPTEST** (IBPSA's open building-control test bench). `anukul_controller.py` is the decision engine. |
| `india/` | Builds a **New Delhi** version of the BOPTEST office by swapping in ISHRAE-2014 Delhi weather. |
| `real_data/` | Runs Anukul's Sense/Decide rules over a year of **real** office data (CU-BEMS, Bangkok, 2019). |
| `bacnet/` | Shows the Act step over real **BACnet/IP**: read points, write a set point at priority 13, operator override wins, relinquish. |
| `hardware/` | ESP32 room node firmware (CO₂ + presence + fan relay) for the physical demo kit. |
| `app/` | The facility-manager console (single HTML file) and the script that fills it with results. |
| `results/` | KPI tables and charts produced by the runs. |
| `docs/` | Plain-English guide, architecture diagram. |

## The four rules

| Rule | When it fires | What it changes |
|---|---|---|
| Night pre-cool | 02:00–06:00, hot day forecast (> 24 °C), outdoor ≥ 3 °C cooler than the warmest zone | AHU runs on 100 % outdoor air, no mechanical cooling |
| Supply-air reset | Occupied hours | Supply air drifts up from 12 °C (max 16 °C) while no zone asks for cooling; steps down when zones ask; held while CO₂ is high |
| Fresh air on demand | Hot hours, or any time CO₂ passes 750 ppm | Outdoor-air damper follows forecast occupancy + measured CO₂ |
| Comfort guard | Occupied hours (Comfort mode only) | Zone set points 20.2 / 23.8 °C, just inside the 20–24 °C band |

*Eco mode* = the first three rules. *Comfort mode* = all four.

## Running it

Requirements: Linux x86-64, Python 3.11+, `pip install fmpy pandas==2.2.3 numpy scipy pytz matplotlib BAC0`.
BOPTEST itself: `git clone https://github.com/ibpsa/project1-boptest`. The FMU needs `libgfortran.so.4`
(Ubuntu package `libgfortran4`). No Docker is needed: `boptest/pyfmi.py` is a small stand-in for pyfmi built on FMPy.

```bash
export BOPTEST_DIR=/path/to/project1-boptest
python boptest/runner.py typical_cool_day baseline out_base.json
python boptest/runner.py typical_cool_day "anukul:night,dcv,sat" out_eco.json
python boptest/runner.py typical_cool_day anukul out_comfort.json
```

Delhi climate: download `IND_DL_New.Delhi-Safdarjung.AP.421820_ISHRAE2014.zip` from climate.onebuilding.org,
then `python india/make_delhi_fmu.py <path to .epw>` and run with `BOPTEST_CASE=multizone_office_simple_air_delhi`
and scenarios `delhi_peak_cool`, `delhi_monsoon`, `delhi_spring` (set `MAX_STEPS` to 672, 576 and 1056).
(The ISHRAE weather file is licensed and is not redistributed here.)

Real data: download `2019Floor2.csv` and `2019Floor7.csv` from the CU-BEMS figshare record
(doi:10.6084/m9.figshare.11726517) into `data/cubems/`, then `python real_data/cubems_waste.py`.

BACnet demo: `python bacnet/bacnet_demo.py` (runs two BACnet devices on 127.0.0.1).

## Limits of this prototype

- BOPTEST's office has the same occupancy every day, including weekends, so savings that come from empty
  weekends and holidays are not counted.
- The Delhi runs keep the Chicago-sized HVAC plant; only the weather changes. The simulation stalls numerically later in some Delhi windows, so Delhi tests are 11 days (spring), 7 days (peak summer) and 6 days (monsoon, Eco only).
- Real-data overcooling savings use BEE's ~6 % per °C figure (and half of it as a low case); they are estimates,
  not measurements.
- The ESP32 firmware has not yet been compiled on hardware.

## Data and tools credited

BOPTEST (IBPSA Project 1, BSD licence) · CU-BEMS dataset (Pipattanasomporn et al., *Scientific Data* 2020, CC BY 4.0) ·
ISHRAE 2014 weather via climate.onebuilding.org · FMPy · BAC0 / bacpypes3.
