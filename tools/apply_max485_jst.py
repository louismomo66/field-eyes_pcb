"""MAX485ESA+T on a 5 V rail, SV1 programming header and 4-pin JST XH connectors, as on the old board (security.sch).
Edits field_eyes_v2.kicad_sch in place."""
import sys
sys.path.insert(0, __import__('os').path.dirname(__file__))
from kedit import Schematic, prop
from sexp import find, q

PATH = sys.argv[1]
s = Schematic(PATH)
s.globals.add('+5V_SENS')

# MAX485ESA+T as the project's own symbol (the library MAX485E is only a variant of another symbol)
import copy, os
from kedit import flatten
from sexp import parse, dump
def retarget(sym, prefix):
    sym[1] = q(prefix + 'MAX485ESA+T')
    for e in sym:
        if isinstance(e, list) and e and e[0] == 'symbol':
            e[1] = q(e[1].strip('"').replace('MAX485E_', 'MAX485ESA+T_', 1))
    for p in find(sym, 'property'):
        k = p[1].strip('"')
        if k == 'Value': p[2] = q('MAX485ESA+T')
        if k == 'Footprint': p[2] = q('Package_SO:SOIC-8_3.9x4.9mm_P1.27mm')
        if k == 'Description': p[2] = q('RS-485/RS-422 transceiver, 5 V, SO-8 (the MAX485ESA+T used on the old board)')
        if k == 'Datasheet': p[2] = q('~')
    return sym
base = flatten('Interface_UART', 'MAX485E')
s.libs.append(retarget(copy.deepcopy(base), 'field_eyes:'))
libpath = os.path.join(os.path.dirname(os.path.abspath(PATH)), 'field_eyes.kicad_sym')
lib = parse(open(libpath).read())[0]
if not any(e[1].strip('"') == 'MAX485ESA+T' for e in find(lib, 'symbol')):
    lib.append(retarget(copy.deepcopy(base), ''))
    open(libpath, 'w').write(dump(lib) + '\n')
JST = 'field_eyes:JST_XH_04_LongPad'
SOIC8 = 'Package_SO:SOIC-8_3.9x4.9mm_P1.27mm'

def where(ref):
    at = find(s.symbol(ref), 'at')[0]
    return float(at[1]), float(at[2])

# ---------------------------------------------------------------- programming header: SV1 (old pin order)
x, y = where('J201')
s.remove('J201')
s.place('Connector_Generic:Conn_02x03_Odd_Even', 'SV1', 'PROG (as old SV1)', x, y, 0,
        {'1': 'PROG_DTR', '2': '+3V3', '3': 'U0_TXD', '4': 'U0_RXD', '5': 'PROG_RTS', '6': 'GND'},
        'field_eyes:MA03-2', ref_at=(x - 5, y - 6), val_at=(x - 5, y + 8), stubs={'2': 15.24})

# ---------------------------------------------------------------- OLED -> X3, DHT22 -> X4 (old pin order)
x, y = where('J202'); s.remove('J202')
s.place('Connector_Generic:Conn_01x04', 'X3', 'OLED (3V3 GND SDA SCL)', x, y, 0,
        {'1': '+3V3', '2': 'GND', '3': 'I2C_SDA', '4': 'I2C_SCL'}, JST, ref_at=(x + 3, y - 4), val_at=(x + 3, y + 4))
x, y = where('J203'); s.remove('J203')
s.place('Connector_Generic:Conn_01x04', 'X4', 'DHT22 (NC 3V3 DATA GND)', x, y, 0,
        {'1': 'NC', '2': '+3V3_SW', '3': 'DHT_DATA', '4': 'GND'}, JST, ref_at=(x + 3, y - 4), val_at=(x + 3, y + 4), stubs={'2': 17.78})

# ---------------------------------------------------------------- RS485: MAX485ESA+T on +5V_SENS
BUSES = [  # bus, tx net, rx net, chip, enable/bias resistors, decoupling cap, connector (old name), sensor
    ('RS1', 'SMT_TX', 'SMT_RX', 'U401', ('R402', 'R403'), 'C401', 'J401', 'X2', 'SMT100', ('R423', 'R424'), 467.36),
    ('RS2', 'NPK_TX', 'NPK_RX', 'U402', ('R412', 'R413'), 'C402', 'J402', 'X1', '7-in-1 NPK', ('R425', 'R426'), 548.64)]
for bus, tx, rx, chip, (r_en, r_bias), cap, jold, jnew, sensor, (r_up, r_dn), ydiv in BUSES:
    # the chip
    x, y = where(chip); s.remove(chip)
    s.place('field_eyes:MAX485ESA+T', chip, 'MAX485ESA+T', x, y, 0,
            {'8': '+5V_SENS', '5': 'GND', '4': tx, '1': f'{bus}_RO', '2': f'{bus}_EN', '3': f'{bus}_EN', '6': f'{bus}_AI', '7': f'{bus}_BI'},
            SOIC8, ref_at=(x - 5, y - 18), val_at=(x - 5, y + 18))
    # pull-ups and decoupling move to the 5 V rail
    for ref, val, a, b in ((r_en, '10k', '+5V_SENS', f'{bus}_EN'), (r_bias, '4.7k', '+5V_SENS', f'{bus}_AI')):
        x, y = where(ref); s.remove(ref); s.R(ref, val, x, y, a, b)
    x, y = where(cap); s.remove(cap); s.C(cap, '100nF', x, y, '+5V_SENS', 'GND')
    # RO swings 0-5 V; the ESP32 pin is not 5 V tolerant: 3.3k + 6.8k divider -> 3.4 V
    s.R(r_up, '3.3k', 518.16, ydiv, f'{bus}_RO', rx)
    s.R(r_dn, '6.8k', 574.04, ydiv, rx, 'GND')
    # field connector: JST XH 4-pin, 1 A, 2 B, 3 +12 V, 4 GND (old X1/X2)
    x, y = where(jold); s.remove(jold)
    s.place('Connector_Generic:Conn_01x04', jnew, f'{sensor} (A B 12V GND)', x, y, 0,
            {'1': f'{bus}_A', '2': f'{bus}_B', '3': '+12V_SENS', '4': 'GND'}, JST, ref_at=(x + 3, y - 4), val_at=(x + 3, y + 4))

# ---------------------------------------------------------------- 5 V for the MAX485s: 78L05 on the 12 V sensor rail
s.place('Regulator_Linear:L78L05_SOT89', 'U405', 'L78L05', 739.14, 454.66, 0,
        {'3': '+12V_SENS', '2': 'GND', '1': '+5V_SENS'}, 'Package_TO_SOT_SMD:SOT-89-3', ref_at=(734, 448), val_at=(742, 448))
s.C('C408', '330nF 25V', 716.28, 464.82, '+12V_SENS', 'GND')
s.C('C409', '1uF', 762.0, 464.82, '+5V_SENS', 'GND')

# ---------------------------------------------------------------- notes that mentioned the old parts
for e in find(s.root, 'text'):
    t = e[1].strip('"').replace('\\n', '\n')
    new = t
    if t.startswith('SP3485 (3.3 V'):
        new = ('MAX485ESA+T (the chip on the old board) on +5V_SENS, made by U405 (78L05) from the 12 V sensor rail, so it only has power\n'
               'while SENS_EN is on. RO swings 0-5 V: the 3.3k + 6.8k divider gives the ESP32 3.4 V (its pins are not 5 V tolerant).\n'
               'Direction is automatic: TX idle-high turns the MMBT3904 on and holds DE/RE low (receive); a 0 bit releases DE so the driver\n'
               'pulls the bus low; 1 bits come from the 4.7k bias. 10 R + SM712 protect the field cable. 120 R not fitted (short cable, 9600 baud).\n'
               'Connectors X1 (7-in-1) and X2 (SMT100) are 4-pin JST XH, pin 1 A, 2 B, 3 +12 V, 4 GND, like the old board.\n'
               'Firmware: set the TX pins low/input before switching the sensors off, or they feed the unpowered chips.')
    new = new.replace('  - MAX485 (5 V) -> SP3485 (3.3 V); sensors and RS485 switched off between readings.',
                      '  - RS485 keeps the MAX485ESA+T (5 V from a 78L05 on the sensor rail); sensors and RS485 switched off between readings.')
    new = new.replace('-> +12V_SENS (soil sensors) -> 78L09 -> 8.7 V valve reservoir (MX1508)',
                      '-> +12V_SENS (soil sensors) -> 78L05 -> +5V_SENS (MAX485) and -> 78L09 -> 8.7 V valve reservoir (MX1508)')
    if new != t:
        e[1] = q(new)
s.save()
print('done')
