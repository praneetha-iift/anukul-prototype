"""Anukul 'Act' layer over real BACnet/IP (the protocol most building management systems speak).

Runs two BACnet devices on this machine:
  * "BMS-AHU-1"   - a stand-in for an existing building controller (device 1001, port 47809)
                    exposing zone temperature, CO2, cooling set point and outdoor-air damper.
  * "Anukul edge" - the Anukul gateway (port 47810). It READS the points, DECIDES with the same
                    rules used in the BOPTEST controller, and WRITES the set point back at
                    BACnet priority 13, so any human/operator command (priority 8) always wins.
Then it RELINQUISHES its command, handing control back to the BMS - the safety feature FMs ask about.
"""
import asyncio, BAC0
from BAC0.core.devices.local.factory import analog_input, analog_value, ObjectFactory

BMS = '127.0.0.1:47809'
DEV = 1001


async def main():
    ObjectFactory.clear_objects()
    analog_input(instance=1, name='Zone-East-Temp', presentValue=21.6, properties={'units': 'degreesCelsius'})
    analog_input(instance=2, name='Zone-East-CO2', presentValue=910, properties={'units': 'partsPerMillion'})
    analog_value(instance=1, name='Zone-East-CoolSP', presentValue=22.0, is_commandable=True,
                 relinquishDefault=22.0, properties={'units': 'degreesCelsius'})
    obj = analog_value(instance=2, name='AHU-OA-Damper', presentValue=32.0, is_commandable=True,
                       relinquishDefault=32.0, properties={'units': 'percent'})
    async with BAC0.start(ip='127.0.0.1/24', port=47809, deviceId=DEV, localObjName='BMS-AHU-1') as bms:
        obj.add_objects_to_application(bms)
        async with BAC0.start(ip='127.0.0.1/24', port=47810, deviceId=2001, localObjName='Anukul-edge') as anukul:
            await asyncio.sleep(1)
            rd = lambda p: anukul.read(f'{BMS} {p} presentValue')
            # ---- SENSE
            T = await rd('analogInput 1'); co2 = await rd('analogInput 2')
            sp = await rd('analogValue 1'); oa = await rd('analogValue 2')
            print(f'SENSE  zone temp {T:.1f} C | CO2 {co2:.0f} ppm | cooling set point {sp:.1f} C | OA damper {oa:.0f} %')
            # ---- DECIDE (same rules as the BOPTEST controller)
            new_sp = 23.8 if (sp < 23.0 and T < 23.0) else sp   # zone cold & set point below band -> raise (BEE default 24 C)
            new_oa = min(60.0, oa + 0.2 * (co2 - 750))     # CO2 above 750 ppm target -> more outdoor air
            print(f'DECIDE zone at {T:.1f} C is overcooled -> cooling set point {sp:.1f} -> {new_sp:.1f} C ; '
                  f'CO2 {co2:.0f} > 750 ppm -> OA damper {oa:.0f} -> {new_oa:.0f} %')
            # ---- ACT: write at priority 13 (below operator priority 8)
            await anukul._write(f'{BMS} analogValue 1 presentValue {new_sp} - 13')
            await anukul._write(f'{BMS} analogValue 2 presentValue {new_oa:.1f} - 13')
            await asyncio.sleep(0.5)
            print(f'ACT    BMS now reports set point {await rd("analogValue 1"):.1f} C, OA damper {await rd("analogValue 2"):.0f} %')
            # ---- operator override at priority 8 beats Anukul
            await anukul._write(f'{BMS} analogValue 1 presentValue 22.5 - 8')
            await asyncio.sleep(0.5)
            print(f'OVERRIDE operator writes 22.5 C at priority 8 -> BMS uses {await rd("analogValue 1"):.1f} C (human wins)')
            await anukul._write(f'{BMS} analogValue 1 presentValue null - 8')
            # ---- RELINQUISH: Anukul hands control back
            await anukul._write(f'{BMS} analogValue 1 presentValue null - 13')
            await anukul._write(f'{BMS} analogValue 2 presentValue null - 13')
            await asyncio.sleep(0.5)
            print(f'RELEASE Anukul relinquishes -> BMS back to its own default: set point {await rd("analogValue 1"):.1f} C, '
                  f'damper {await rd("analogValue 2"):.0f} %')

asyncio.run(main())
