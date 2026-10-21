# Field Eyes v2: full board schematic (KiCad 9)

Open `field_eyes_v2.kicad_pro` in KiCad 9. The whole circuit is **one flat schematic** (`field_eyes_v2.kicad_sch`): all 168 parts are on a single page, in four framed sections. The same page is in `field_eyes_v2.pdf`, and the parts list is in `field_eyes_v2_bom.csv`.

The design has 168 parts. KiCad's electrical rules check (ERC) reports 0 violations, and every net connects at least two pins.

**Status: schematic only.** There is no PCB layout yet. Nothing has been built or tested.

| Section (frame on the page) | Contents |
|---|---|
| Top of the page | Title, power tree, what changed from the old board, PCB layout notes |
| 1 Power (parts R1xx, C1xx...) | 6 V solar panel → CN3791 MPPT charger → 18650 cell with DW01A + FS8205 protection. XC6220 3.3 V regulator. AO3401A-switched +3V3_SW and +12V_SENS (MT3608 boost). Battery voltage, temperature and charge-status sensing. |
| 2 ESP32 (2xx) | ESP32-WROOM-32D. EN delay. Programming header **SV1** (the same 2 × 3 header and pin order as the old board: DTR, 3V3, TX, RX, RTS, GND) with auto-reset. OLED (**X3**) and DHT22 (**X4**) on 4-pin JST XH connectors with the old board's pinouts. 4 × M3 mounting holes. ESP32 pin map. |
| 3 Modem (3xx) | A7672S running straight from the cell, with 470 µF and the SIMCom capacitor set. PWRKEY and RESET drivers. UART level shifters. RI wake. Network LED. SIM holder with 22 Ω resistors and ESD. U.FL antenna with matching pads. Service header for modem firmware updates. |
| 4 Sensors and valve (4xx) | 2 × **MAX485ESA+T** RS485 (SMT100 on **X2**, 7-in-1 on **X1**) with automatic direction and SM712 protection. X1/X2 are 4-pin JST XH, pin 1 A, 2 B, 3 +12 V, 4 GND, as on the old board. A 78L05 (U405) makes the 5 V the MAX485 needs; dividers (3.3k/6.8k) bring its receive output down to 3.4 V for the ESP32. MX1508 driver for the latching valve (the chip from your mini-L298N module). |

The first version had four separate sheets behind placeholder boxes. Those files, and the board file as it was, are kept in `old_hierarchical/`; the circuit is identical (every net connects the same pins) and the board was relinked to the flat schematic.

`field_eyes.kicad_sym` holds custom symbols for the CN3791, FS8205, A7672S, SIM holder and SMF05C. The A7672S and SIM-holder footprints in `field_eyes.pretty` are copied from your current board, so they match what was already fabricated.

## Main decisions

- **Supply:** one Li-ion cell (VSYS 3.0–4.2 V).
  - The A7672S runs straight from it, as in SIMCom's reference design. That removes the MP2338 buck, the LM1117 and the D6/D7 diode drop.
  - Solar MPPT charging and cell protection are on the board.
  - Details and the battery-life estimate are in `../power_v2/README.md`. That earlier power-only project is now part of this one.
- **Everything that isn't needed is off by default.** The modem stays off until GPIO26 presses its power key. Sensors, RS485 chips, the DHT22 and the 12 V boost only get power while SENS_EN (GPIO13) is high.
- **Wake on message:** the modem's RI line goes to GPIO35 (an RTC pin), so the ESP32 can sleep and still react to a valve command immediately.
- **RS485:** the MAX485ESA+T from your old board. It needs 5 V, which this board no longer has, so U405 (78L05) makes +5V_SENS from the 12 V sensor rail; it is only powered while SENS_EN is on. The chip's receive output swings 0–5 V and the ESP32 pins are not 5 V tolerant, so each channel has a 3.3k/6.8k divider. Your auto-direction transistor trick is kept. The 120 Ω terminations are drawn but not fitted.
- **Valve:** the **MX1508**, the chip on your "mini L298N" driver board, is now on this board, using channel 1.
  - Same inputs as the module: IN1 = GPIO27 → INA1, IN2 = GPIO5 → INB1. H/L opens, L/H closes, both low = standby (< 0.1 µA). The firmware doesn't change.
  - The MX1508's motor supply must stay below 10 V (2–9.6 V for normal use), so it can't take the 12 V sensor rail.
  - Instead, a 78L09 charges a 4700 µF capacitor from the 12 V boost to about 8.7 V. It limits the current to about 0.1 A, so the battery protection can't trip. The capacitor then supplies the coil pulse, and a diode keeps it charged while the boost is off.
  - Solder jumper JP401 picks the valve supply: pads 1–2 (default) = 8.7 V for 9 V valves; pads 2–3 = the battery (3.0–4.2 V) for 3.6–6 V valves.
  - The chip's logic runs from +3V3, so the ESP32's 3.3 V signals are always within its input range. The second channel is unused (inputs tied low).
- **SIM, antenna and modem-service pads** follow the SIMCom A7672X hardware manual (figures 10, 13, 16, 22 and section 4.6).
- **GPS antenna:** kept, with the same circuit as the old board. U.FL connector **J304** takes an active antenna, fed from the modem's 2.8 V through R318 (0 Ω) and L301 (56 nH); C313 (33 pF) blocks the DC. The modem's built-in GNSS is linked to its UART3 by R320/R321 (1k), GNSS_PWRCTL goes to MK_IN_3 through R319 (10k), and 1V8_GNSS and GNSS_VBKP are powered. The firmware doesn't use GPS yet (the location is fixed). For a passive antenna, fit C313 only and leave R318/L301 off.

## Check these assumptions before ordering

1. **Valve voltage.** Check what supply your valve ran from on the module.
   - Up to about 9 V: leave JP401 on 1–2.
   - 3.6–6 V: move JP401 to 2–3.
   - A 12 V valve can't be driven by the MX1508 at its rated voltage, because the chip's limit is 10 V.
   - If the valve doesn't latch reliably, raise C403 to 6800–10000 µF.
   - The MX1508 channel is rated 1.5 A continuous and 2 A peak, so the coil should be at least about 5 Ω.
2. **Sensors at 12 V.** The Gemho 7-in-1 needs 9–18 V; the SMT100 accepts 4–24 V.
3. **GPS antenna type.** The bias circuit assumes an active antenna, like the old board. The GPS trace from J304 to the modem should be short and 50 Ω when you route it.

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
   - SM712s next to the JST sensor connectors X1/X2.
3. Route the board, pour ground on the bottom layer, then run DRC.
# field-eyes_pcb

## Connectors (as on the old board)

| Ref | What | Pins |
|---|---|---|
| SV1 | Programming, 2 × 3 header (MA03-2) | 1 DTR, 2 3V3, 3 TX0, 4 RX0, 5 RTS, 6 GND |
| X1 | 7-in-1 NPK sensor, JST XH 4-pin | 1 A, 2 B, 3 +12 V, 4 GND |
| X2 | SMT100, JST XH 4-pin | 1 A, 2 B, 3 +12 V, 4 GND |
| X3 | OLED, JST XH 4-pin | 1 3V3, 2 GND, 3 SDA, 4 SCL |
| X4 | DHT22, JST XH 4-pin | 1 not connected, 2 3V3 (switched), 3 DATA, 4 GND |

The solar input (J101) and the valve coil (J403) stay as 2-pin screw terminals because they carry more current. The board's old X5 (RGB LED / valve module) is gone: the valve driver is now on the board.

The board file was updated to match: the footprints are in `field_eyes.pretty`, which now includes the JST and SV1 footprints copied from your old board. The new parts were placed in free spots and are provisional. Files from before this change are in `backups/`.

## Board layout (follows the old design, sized for the enclosure)

**Enclosure:** DFRobot plastic project box, 5.83 × 3.70 × 2.36 in = about **148 × 94 × 60 mm** outside (the shop page gives only these overall figures; the interior is roughly 142 × 88 mm if the walls are about 3 mm).

The board is **118.3 × 68 mm** with 4 mm rounded corners. That leaves about 12 mm to the walls on the long sides and 10 mm on the short sides, which should keep it clear of the lid-screw posts in the corners. **Measure the inside of your box and its posts before ordering boards.** The 18650 holder (88 mm) lies on the back along the long side; the tallest part on the top is the 13 mm valve capacitor C403, so cell, board and parts stack to roughly 43 mm of the 55 mm inside height (also worth checking).

It is the old board's 100 × 60 mm layout, widened by 18 mm on the left and 8 mm at the bottom for the new circuits. Everything that was on the old board keeps its old arrangement:

- ESP32 left of centre with SV1 above it, and the GPS connector (J304) with its parts on the top edge
- the modem on the right, with the LTE antenna connector (J301) on the right edge
- the SIM tray (J302) on the **bottom edge** near the right corner, with its protection and resistors beside it
- the sensor connectors X2 (SMT100), X1 (7-in-1) and X4 (DHT22) along the bottom edge; X3 (OLED) beside the ESP32
- the modem control transistors in a row above the modem, the network LED and its transistor on the right edge, and the modem supply capacitors at the bottom right

New on the left: the solar charger, battery protection, 3.3 V regulator, 12 V boost and switches, the valve driver with its big capacitor, and the solar (J101) and valve (J403) terminals. The 18650 holder is on the back, with its temperature sensor.

All 168 parts are placed with no overlaps. There are no tracks yet. A smaller board also places (106 × 64 mm) but would be crowded and hard to route. `tools/place_like_old.py <board> <out> <extra width> <height>` redoes the placement at another size; the previous layouts are in `backups/`.

## No buttons

The RESET and BOOT buttons were removed. The board is reset and put in boot mode by the programming adapter on SV1 (RTS drives EN, DTR drives IO0, through the two-transistor auto-reset circuit), so flashing needs an adapter that brings out DTR and RTS on pins 1 and 5. Without a button there is no manual reset: switching the power off and on (or the adapter's RTS) does it.

## Even placement

After the first placement the parts were respread so that no area is crowded while others are empty: parts push each other apart with a light pull towards the parts they are wired to, and the parts that sit where they did on the old board (ESP32, modem, SIM tray, connectors) stay fixed. Parts keep out of the ESP32 antenna zone along the top edge and away from the battery holder's peg holes. Result: the unevenness of the part density across the free area is about halved, the wiring is shorter (signal nets about 8% less total length), and nothing overlaps. `tools/spread_parts.py` does it (export with `tools/export_placement.py`, apply with `tools/apply_positions.py`); the earlier placement is in `backups/field_eyes_v2.before_spreading.kicad_pcb`.

## GPS antenna corridor and RF lines

An antenna line needs a controlled 50 Ω track. On this 1.6 mm two-layer board that is a **microstrip about 3.0 mm wide** (calculated for FR4, εr 4.5, with the unbroken ground plane on the bottom layer under it), kept clear of other copper by about 1.5 mm each side, as short as possible, with ground vias along both sides, and tapered down to the 0.64 mm pad of the modem and the connector's centre pad. So the GPS part of the board is laid out around it:

- J304 (U.FL) sits on the top edge **just outside the ESP32 antenna zone**, with its centre pin facing the modem; the modem's GPS pad (P$90) is on the modem's top-left edge about 9 mm below it.
- The line runs from J304 straight down to the pad through **C313 (33 pF, in line)**: about 12 mm in all.
- L301 and R318 (the antenna bias) sit off to the side, away from the line; the bias is DC and can take any route.
- A **clear corridor** of 13 × 10 mm around the line holds no other part, and the spreading tool keeps it that way. The area under it on the bottom layer is free for the ground plane.

Route `/GPS_ANT`, `/GPS_SIG` (and the LTE nets `/RF_ANT`, `/ANT_FEED`) **by hand**, with a 3.0 mm track, not with the autorouter. `tools/dsn_without.py` makes `routing/field_eyes_v2_autoroute.dsn` without those nets and without ground (ground comes from the pours). The LTE line (modem right edge to J301, about 8 mm) needs the same width and clearance; its parts are placed along the straight line to J301, but it was not given a protected corridor of its own.
