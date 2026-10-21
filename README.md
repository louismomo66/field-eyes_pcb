# Field Eyes v2: full board schematic (KiCad 9)

Open `field_eyes_v2.kicad_pro` in KiCad 9. The whole circuit is **one flat schematic** (`field_eyes_v2.kicad_sch`): all 156 parts are on a single page, in four framed sections. The same page is in `field_eyes_v2.pdf`, and the parts list is in `field_eyes_v2_bom.csv`.

The design has 156 parts. KiCad's electrical rules check (ERC) reports 0 violations, and every net connects at least two pins.

**Status: schematic only.** There is no PCB layout yet. Nothing has been built or tested.

| Section (frame on the page) | Contents |
|---|---|
| Top of the page | Title, power tree, what changed from the old board, PCB layout notes |
| 1 Power (parts R1xx, C1xx...) | 6 V solar panel → CN3791 MPPT charger → 18650 cell with DW01A + FS8205 protection. XC6220 3.3 V regulator. AO3401A-switched +3V3_SW and +12V_SENS (MT3608 boost). Battery voltage, temperature and charge-status sensing. |
| 2 ESP32 (2xx) | ESP32-WROOM-32D. EN delay. RESET and BOOT buttons. Auto-reset programming header (same pin order as the old SV1). OLED and DHT22 headers. 4 × M3 mounting holes. ESP32 pin map. |
| 3 Modem (3xx) | A7672S running straight from the cell, with 470 µF and the SIMCom capacitor set. PWRKEY and RESET drivers. UART level shifters. RI wake. Network LED. SIM holder with 22 Ω resistors and ESD. U.FL antenna with matching pads. Service header for modem firmware updates. |
| 4 Sensors and valve (4xx) | 2 × SP3485 RS485 (SMT100, 7-in-1) with automatic direction, SM712 protection and screw terminals. MX1508 driver for the latching valve (the chip from your mini-L298N module). |

The first version had four separate sheets behind placeholder boxes. Those files, and the board file as it was, are kept in `old_hierarchical/`; the circuit is identical (every net connects the same pins) and the board was relinked to the flat schematic.

`field_eyes.kicad_sym` holds custom symbols for the CN3791, FS8205, A7672S, SIM holder and SMF05C. The A7672S and SIM-holder footprints in `field_eyes.pretty` are copied from your current board, so they match what was already fabricated.

## Main decisions

- **Supply:** one Li-ion cell (VSYS 3.0–4.2 V).
  - The A7672S runs straight from it, as in SIMCom's reference design. That removes the MP2338 buck, the LM1117 and the D6/D7 diode drop.
  - Solar MPPT charging and cell protection are on the board.
  - Details and the battery-life estimate are in `../power_v2/README.md`. That earlier power-only project is now part of this one.
- **Everything that isn't needed is off by default.** The modem stays off until GPIO26 presses its power key. Sensors, RS485 chips, the DHT22 and the 12 V boost only get power while SENS_EN (GPIO13) is high.
- **Wake on message:** the modem's RI line goes to GPIO35 (an RTC pin), so the ESP32 can sleep and still react to a valve command immediately.
- **RS485:** SP3485 parts (3.3 V, same pinout as the MAX485). Your existing auto-direction transistor trick is kept. The 120 Ω terminations are drawn but not fitted.
- **Valve:** the **MX1508**, the chip on your "mini L298N" driver board, is now on this board, using channel 1.
  - Same inputs as the module: IN1 = GPIO27 → INA1, IN2 = GPIO5 → INB1. H/L opens, L/H closes, both low = standby (< 0.1 µA). The firmware doesn't change.
  - The MX1508's motor supply must stay below 10 V (2–9.6 V for normal use), so it can't take the 12 V sensor rail.
  - Instead, a 78L09 charges a 4700 µF capacitor from the 12 V boost to about 8.7 V. It limits the current to about 0.1 A, so the battery protection can't trip. The capacitor then supplies the coil pulse, and a diode keeps it charged while the boost is off.
  - Solder jumper JP401 picks the valve supply: pads 1–2 (default) = 8.7 V for 9 V valves; pads 2–3 = the battery (3.0–4.2 V) for 3.6–6 V valves.
  - The chip's logic runs from +3V3, so the ESP32's 3.3 V signals are always within its input range. The second channel is unused (inputs tied low).
- **SIM, antenna and modem-service pads** follow the SIMCom A7672X hardware manual (figures 10, 13, 16, 22 and section 4.6).
- **GNSS is not used** (the location is fixed in the firmware), so the GPS antenna, its LNA supply and the GNSS pins were dropped.

## Check these assumptions before ordering

1. **Valve voltage.** Check what supply your valve ran from on the module.
   - Up to about 9 V: leave JP401 on 1–2.
   - 3.6–6 V: move JP401 to 2–3.
   - A 12 V valve can't be driven by the MX1508 at its rated voltage, because the chip's limit is 10 V.
   - If the valve doesn't latch reliably, raise C403 to 6800–10000 µF.
   - The MX1508 channel is rated 1.5 A continuous and 2 A peak, so the coil should be at least about 5 Ω.
2. **Sensors at 12 V.** The Gemho 7-in-1 needs 9–18 V; the SMT100 accepts 4–24 V.
3. **Your A7672S variant.** If you need GNSS later, tell me and I'll put that section back.

## Firmware changes this board needs (not made yet)

| What | Old board | New board |
|---|---|---|
| Modem power key | tied to GND (always on) | **GPIO26**: pulse HIGH 100–500 ms to switch on; switch off with `AT+CPOF` |
| Modem reset | GPIO19 (pulse direction wrong in the current firmware) | GPIO19: HIGH = reset (pulse 2.5 s), idle LOW |
| Sensor power | `SWITCH_PIN` 13 (placeholder) | GPIO13 = SENS_EN, unchanged. Also has to be on ≥ 1 s before every valve pulse, to top up the valve capacitor. |
| Battery voltage | GPIO34, old 78k/2k2 divider | GPIO34 × 2 |
| New inputs/outputs | — | GPIO35 RI wake; GPIO36 charging (low); GPIO39 cell temperature; GPIO14 stop charging |
| RS485 | MAX485 on 5 V | Same UART pins. Set the TX pins low or input before switching sensors off. |

## Next step: PCB layout (in KiCad)

1. In KiCad, open the PCB Editor, then **Tools → Update PCB from Schematic**. All footprints come in with their connections shown as ratsnest lines.
2. **Place parts**, following the layout notes at the top of the schematic page:
   - Keep the charger and boost switching loops tight.
   - Modem VBAT ≥ 2 mm wide, with C301–C306 at its pins.
   - 50 Ω RF trace from the modem to the U.FL.
   - ESP32 antenna over the board edge with no copper underneath.
   - Battery-temperature NTC (TH101) under the cell.
   - SM712s at the screw terminals.
3. Route the board, pour ground on the bottom layer, then run DRC.
# field-eyes_pcb
