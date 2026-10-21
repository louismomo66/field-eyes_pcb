"""Adds the GPS (GNSS) antenna circuit back, as on the old board: U.FL antenna connector, 33 pF DC block, 56 nH + 0 R active-antenna
bias from the modem's 2.8 V, 10 k on GNSS_PWRCTL, 1 k links between the modem's UART3 and its GNSS UART. Extends the A7672S symbol."""
import sys, os, re, copy, subprocess, tempfile
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from kedit import Schematic, prop
from sexp import parse, dump, find, q, fmt

PATH = sys.argv[1]
HERE = os.path.dirname(os.path.abspath(PATH))
OX, OY = 7.62, 416.56               # origin of the modem block on the page

# ---------------------------------------------------------------- current nets of the modem, from KiCad's netlist
tmp = tempfile.mkdtemp()
net_path = os.path.join(tmp, 'x.net')
subprocess.run(['/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli', 'sch', 'export', 'netlist', '-o', net_path, PATH],
               capture_output=True)
r = parse(open(net_path).read())[0]
pin_net = {}
for n in find(r, 'nets')[0][1:]:
    name = find(n, 'name')[0][1].strip('"')
    for x in find(n, 'node'):
        if find(x, 'ref')[0][1].strip('"') == 'U301':
            pin_net[find(x, 'pin')[0][1].strip('"')] = 'NC' if name.startswith('unconnected') else name.lstrip('/')

s = Schematic(PATH)
sym = s.symbol('U301')
at = find(sym, 'at')[0]
ux, uy = float(at[1]), float(at[2])
old_lib = s.libdef('field_eyes:A7672S')
visible = [p['num'] for p in __import__('kedit').lib_pins(old_lib) if not p['hidden']]
nets = {p: pin_net[p] for p in visible}
print('modem nets carried over:', len(nets))
s.remove('U301')

# ---------------------------------------------------------------- extend the symbol (library file and the copy in the schematic)
NEW_PINS = [  # side, name, number, type, y
    ('L', 'GNSS_PWRCTL', 'P$98', 'output', -10.16), ('L', 'MK_IN_3', 'P$20', 'bidirectional', -12.7),
    ('L', 'GNSS_VBKP', 'P$116', 'power_in', -15.24), ('L', '1V8_GNSS', 'P$97', 'power_in', -17.78),
    ('L', 'VDD_2V8', 'P$99', 'power_out', -20.32),
    ('R', 'GPS_ANT', 'P$90', 'passive', -15.24), ('R', 'GNSS_RXD', 'P$96', 'input', -17.78),
    ('R', 'GNSS_TXD', 'P$95', 'output', -20.32), ('R', 'U3_RXD', 'P$49', 'input', -22.86), ('R', 'U3_TXD', 'P$50', 'output', -25.4)]

def pin_expr(side, name, num, kind, y):
    x, rot = (-20.32, 0) if side == 'L' else (20.32, 180)
    return parse(f'(pin {kind} line (at {fmt(x)} {fmt(y)} {rot}) (length 2.54) '
                 f'(name {q(name)} (effects (font (size 1.27 1.27)))) (number {q(num)} (effects (font (size 1.27 1.27)))))')[0]

def extend(symdef):
    if any(p[2:3] and 'P$90' in dump(p) for p in find(find(symdef, 'symbol')[1], 'pin')):
        return False
    units = find(symdef, 'symbol')
    for rect in find(units[0], 'rectangle'):
        find(rect, 'end')[0][2] = '-30.48'
    for p in find(units[1], 'pin'):
        a = find(p, 'at')[0]
        if a[1] == '0' and a[2] == '-17.78' and a[3] == '90':      # the stacked GND pins at the bottom
            a[2] = '-33.02'
    for np in NEW_PINS:
        units[1].append(pin_expr(*np))
    return True

emb = [e for e in find(s.libs, 'symbol') if e[1].strip('"') == 'field_eyes:A7672S'][0]
extend(emb)
libpath = os.path.join(HERE, 'field_eyes.kicad_sym')
lib = parse(open(libpath).read())[0]
for e in find(lib, 'symbol'):
    if e[1].strip('"') == 'A7672S':
        if extend(e):
            e_desc = [p for p in find(e, 'property') if p[1].strip('"') == 'Description'][0]
            e_desc[2] = q('SIMCom A7672S LTE Cat-1 module with GNSS. Only the pins this design uses are drawn; audio, SPI, camera and keypad pads stay unconnected.')
open(libpath, 'w').write(dump(lib) + '\n')
for p in find(emb, 'property'):
    if p[1].strip('"') == 'Description':
        p[2] = q('SIMCom A7672S LTE Cat-1 module with GNSS. Only the pins this design uses are drawn; audio, SPI, camera and keypad pads stay unconnected.')

nets.update({'P$98': 'GNSS_PWRCTL', 'P$20': 'MK_IN_3', 'P$116': '+3V3', 'P$97': 'VDD_1V8', 'P$99': 'VDD_2V8',
             'P$90': 'GPS_ANT', 'P$96': 'GNSS_RXD', 'P$95': 'GNSS_TXD', 'P$49': 'U3_RXD', 'P$50': 'U3_TXD'})
s.place('field_eyes:A7672S', 'U301', 'A7672S', ux, uy, 0, nets, 'field_eyes:A7672S', ref_at=(ux - 17, uy - 20), val_at=(ux - 17, uy + 30), stubs={'P$116': 17.78})

# ---------------------------------------------------------------- the GNSS antenna circuit
def A(x, y):
    sn = lambda v: round(v / 2.54) * 2.54
    return sn(OX + x), sn(OY + y)
SOIC = None
s.text('GPS ANTENNA (active antenna, as on the old board): the modem\'s 2.8 V feeds the antenna through R318 + L301 (56 nH); C313 blocks the DC.\n'
       'The built-in GNSS UART is linked to UART3 through R320/R321 and GNSS_PWRCTL goes to MK_IN_3 through R319 (SIMCom 3.11). 1V8_GNSS and GNSS_VBKP are powered.\n'
       'For a passive antenna, fit C313 only and do not fit R318/L301 (and send AT+CVAUXS=0).', *A(88, 46))
x, y = A(98, 62);  s.C('C313', '33pF', x, y, 'GPS_ANT', 'GPS_SIG', 'Capacitor_SMD:C_0402_1005Metric')
x, y = A(132, 62); s.place('Connector:Conn_Coaxial', 'J304', 'U.FL GPS', x, y, 0, {'1': 'GPS_SIG', '2': 'GND'},
                           'Connector_Coaxial:U.FL_Hirose_U.FL-R-SMT-1_Vertical', ref_at=(x + 3, y - 4), val_at=(x + 3, y + 5))
x, y = A(98, 72);  s.place('Device:L', 'L301', '56nH', x, y, 90, {'1': 'GPS_SIG', '2': 'GPS_BIAS'}, 'Inductor_SMD:L_0805_2012Metric',
                           ref_at=(x, y - 3), val_at=(x, y + 3.5), just='center')
x, y = A(132, 72); s.R('R318', '0R', x, y, 'GPS_BIAS', 'VDD_2V8')
x, y = A(98, 82);  s.R('R319', '10k', x, y, 'GNSS_PWRCTL', 'MK_IN_3')
x, y = A(132, 82); s.R('R320', '1k', x, y, 'GNSS_RXD', 'U3_RXD')
x, y = A(98, 92);  s.R('R321', '1k', x, y, 'GNSS_TXD', 'U3_TXD')

# ---------------------------------------------------------------- notes
for e in find(s.root, 'text'):
    t = e[1].strip('"').replace('\\n', '\n')
    n = t.replace('GNSS, audio, SPI, camera and keypad pins are not used and stay unconnected (not drawn on the symbol).',
                  'Audio, SPI, camera and keypad pins are not used and stay unconnected (not drawn on the symbol). GPS: see the GPS ANTENNA block.')
    n = n.replace('; GNSS antenna dropped (location is fixed in firmware).', '; GPS antenna kept (U.FL J304, active-antenna bias as on the old board).')
    n = n.replace('  - EN reset delay and auto-reset programming added; GNSS antenna dropped (location is fixed in firmware).',
                  '  - EN reset delay and auto-reset programming added; GPS antenna kept (U.FL J304, as on the old board).')
    if n != t:
        e[1] = q(n)
s.save()
print('done')
