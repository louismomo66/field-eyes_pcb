"""Edits a flat KiCad 9 schematic: remove a symbol with its wire stubs and labels, place a new one with its nets."""
import math, os, re, copy
from sexp import parse, dump, find, fmt, q, new_uuid

LIBDIR = '/Applications/KiCad/KiCad.app/Contents/SharedSupport/symbols/'
_libs = {}

def libsym(lib, name):
    if lib not in _libs:
        root = parse(open(LIBDIR + lib + '.kicad_sym').read())[0]
        _libs[lib] = {e[1].strip('"'): e for e in find(root, 'symbol')}
    return _libs[lib][name]

def flatten(lib, name, custom=None):
    """symbol definition named lib:name with `extends` resolved (custom: {lib:name -> symbol} from this schematic)"""
    s = copy.deepcopy(libsym(lib, name))
    ext = find(s, 'extends')
    if not ext:
        s[1] = q(lib + ':' + name)
        return s
    parent = flatten(lib, ext[0][1].strip('"'))
    pname = parent[1].strip('"').split(':', 1)[1]
    out = ['symbol', q(lib + ':' + name)]
    for e in parent[2:]:
        if isinstance(e, list) and e and e[0] == 'property':
            continue
        if isinstance(e, list) and e and e[0] == 'symbol':
            e = copy.deepcopy(e)
            e[1] = q(e[1].strip('"').replace(pname + '_', name + '_', 1))
        out.append(e)
    idx = next(i for i, e in enumerate(out) if isinstance(e, list) and e and e[0] == 'symbol')
    out[idx:idx] = find(s, 'property')
    return out

def lib_pins(sym):
    pins = []
    def walk(x):
        for e in x:
            if isinstance(e, list):
                if e and e[0] == 'pin':
                    at = find(e, 'at')[0]
                    hidden = any(isinstance(z, list) and z and z[0] == 'hide' for z in e) or 'hide' in e
                    pins.append(dict(num=find(e, 'number')[0][1].strip('"'), name=find(e, 'name')[0][1].strip('"'),
                                     x=float(at[1]), y=float(at[2]), rot=int(float(at[3])), hidden=hidden))
                else:
                    walk(e)
    walk(sym)
    return pins

def xform(px, py, rot):
    x, y = px, -py
    t = math.radians(rot)
    c, s = round(math.cos(t)), round(math.sin(t))
    return (x * c + y * s, -x * s + y * c)

OUTWARD = {0: (-1, 0), 180: (1, 0), 90: (0, -1), 270: (0, 1)}

def prop(sym, key):
    for p in find(sym, 'property'):
        if p[1].strip('"') == key:
            return p[2].strip('"')
    return ''

class Schematic:
    def __init__(self, path):
        self.path = path
        self.root = parse(open(path).read())[0]
        self.libs = find(self.root, 'lib_symbols')[0]
        self.root_uuid = find(self.root, 'uuid')[0][1].strip('"')
        self.globals = {e[1].strip('"') for e in find(self.root, 'global_label')}
        self.project = None
        for e in find(self.root, 'symbol'):
            for inst in find(e, 'instances'):
                self.project = find(inst, 'project')[0][1].strip('"')
                break
            if self.project:
                break
        self.pwr = 9000

    # ----------------------------------------------------------------------------------- lookup
    def symbol(self, ref):
        for e in find(self.root, 'symbol'):
            if prop(e, 'Reference') == ref:
                return e
        raise KeyError(ref)

    def libdef(self, lib_id):
        for s in find(self.libs, 'symbol'):
            if s[1].strip('"') == lib_id:
                return s
        lib, name = lib_id.split(':')
        s = flatten(lib, name)
        self.libs.append(s)
        return s

    def pin_points(self, sym):
        lid = find(sym, 'lib_id')[0][1].strip('"')
        at = find(sym, 'at')[0]
        sx, sy, rot = float(at[1]), float(at[2]), int(float(at[3]))
        pts = []
        for p in lib_pins(self.libdef(lid)):
            if p['hidden']:
                continue
            ox, oy = xform(p['x'], p['y'], rot)
            pts.append((round(sx + ox, 3), round(sy + oy, 3)))
        return pts

    # ----------------------------------------------------------------------------------- edit
    def remove(self, ref):
        sym = self.symbol(ref)
        pts = set(self.pin_points(sym))
        near = lambda a, b: abs(a[0] - b[0]) < 0.02 and abs(a[1] - b[1]) < 0.02
        gone = [sym]
        ends = []
        for w in find(self.root, 'wire'):
            xy = [(float(p[1]), float(p[2])) for p in find(find(w, 'pts')[0], 'xy')]
            for a, b in (xy, xy[::-1]):
                if any(near(a, p) for p in pts):
                    gone.append(w); ends.append(b)
                    break
        for e in self.root:
            if not isinstance(e, list) or not e:
                continue
            if e[0] in ('label', 'global_label', 'symbol', 'no_connect') and e is not sym:
                at = find(e, 'at')[0]
                pos = (float(at[1]), float(at[2]))
                if e[0] == 'no_connect' and any(near(pos, p) for p in pts):
                    gone.append(e)
                elif any(near(pos, p) for p in ends):
                    if e[0] in ('label', 'global_label') or (e[0] == 'symbol' and find(e, 'lib_id')[0][1].strip('"') in ('power:GND', 'power:PWR_FLAG')):
                        gone.append(e)
        for g in gone:
            self.root.remove(g) if g in self.root else None
        return len(gone)

    def _add(self, e):
        i = next(k for k, x in enumerate(self.root) if isinstance(x, list) and x and x[0] == 'sheet_instances')
        self.root.insert(i, e)

    def _text(self, s):
        return parse(s)[0]

    def wire(self, x1, y1, x2, y2):
        self._add(self._text(f'(wire (pts (xy {fmt(x1)} {fmt(y1)}) (xy {fmt(x2)} {fmt(y2)})) (stroke (width 0) (type default)) (uuid {q(new_uuid())}))'))

    def label(self, net, x, y, d):
        ang = {(-1, 0): 180, (1, 0): 0, (0, -1): 90, (0, 1): 270}[d]
        if net in self.globals:
            gj = 'left' if ang in (0, 90) else 'right'
            self._add(self._text(
                f'(global_label {q(net)} (shape passive) (at {fmt(x)} {fmt(y)} {ang}) (fields_autoplaced yes) '
                f'(effects (font (size 1.27 1.27)) (justify {gj})) (uuid {q(new_uuid())}) '
                f'(property "Intersheetrefs" "${{INTERSHEET_REFS}}" (at {fmt(x)} {fmt(y)} 0) (effects (font (size 1.27 1.27)) (justify left) (hide yes))))'))
        else:
            just = 'left bottom' if ang in (0, 90) else 'right bottom'
            self._add(self._text(f'(label {q(net)} (at {fmt(x)} {fmt(y)} {ang}) (fields_autoplaced yes) '
                                 f'(effects (font (size 1.27 1.27)) (justify {just})) (uuid {q(new_uuid())}))'))

    def text(self, s, x, y, size=1.27, bold=False):
        b = ' (bold yes)' if bold else ''
        self._add(self._text(f'(text {q(s)} (exclude_from_sim no) (at {fmt(x)} {fmt(y)} 0) '
                             f'(effects (font (size {size} {size}){b}) (justify left top)) (uuid {q(new_uuid())}))'))

    def place(self, lib_id, ref, value, x, y, rot=0, nets=None, fp='', ref_at=None, val_at=None, just='left', dnp=False, stubs=None):
        ld = self.libdef(lib_id)
        power = ref.startswith('#')
        ds = prop(ld, 'Datasheet') or '~'
        rx, ry = ref_at if ref_at else (x + 5.08, y - 1.27)
        vx, vy = val_at if val_at else (x + 5.08, y + 1.27)
        fa = 90 if rot in (90, 270) else 0
        jt = '' if just == 'center' else f' (justify {just})'
        hide_r = ' (hide yes)' if power else ''
        hide_v = ' (hide yes)' if power else ''
        props = [f'(property "Reference" {q(ref)} (at {fmt(rx)} {fmt(ry)} {fa}) (effects (font (size 1.27 1.27)){jt}{hide_r}))',
                 f'(property "Value" {q(value)} (at {fmt(vx)} {fmt(vy)} {fa}) (effects (font (size 1.27 1.27)){jt}{hide_v}))',
                 f'(property "Footprint" {q(fp)} (at {fmt(x)} {fmt(y)} 0) (effects (font (size 1.27 1.27)) (hide yes)))',
                 f'(property "Datasheet" {q(ds)} (at {fmt(x)} {fmt(y)} 0) (effects (font (size 1.27 1.27)) (hide yes)))',
                 f'(property "Description" "" (at {fmt(x)} {fmt(y)} 0) (effects (font (size 1.27 1.27)) (hide yes)))']
        pins = lib_pins(ld)
        pin_uuids = ' '.join(f'(pin {q(p["num"])} (uuid {q(new_uuid())}))' for p in pins)
        bom = 'no' if power else 'yes'
        self._add(self._text(
            f'(symbol (lib_id {q(lib_id)}) (at {fmt(x)} {fmt(y)} {rot}) (unit 1) (exclude_from_sim no) (in_bom {bom}) (on_board {bom}) '
            f'(dnp {"yes" if dnp else "no"}) (uuid {q(new_uuid())}) ' + ' '.join(props) + ' ' + pin_uuids +
            f' (instances (project {q(self.project)} (path {q("/" + self.root_uuid)} (reference {q(ref)}) (unit 1)))))'))
        if nets is None:
            return
        done = set()
        for p in pins:
            if p['hidden']:
                continue
            net = nets.get(p['num'])
            if net is None:
                raise SystemExit(f'{ref} pin {p["num"]} ({p["name"]}) has no net')
            ox, oy = xform(p['x'], p['y'], rot)
            px, py = x + ox, y + oy
            if (round(px, 3), round(py, 3)) in done:
                continue
            done.add((round(px, 3), round(py, 3)))
            if net == 'NC':
                self._add(self._text(f'(no_connect (at {fmt(px)} {fmt(py)}) (uuid {q(new_uuid())}))'))
                continue
            lx, ly = OUTWARD[p['rot']]
            dx, dy = xform(lx, ly, rot)
            ln = (stubs or {}).get(p['num'], 2.54)
            ex, ey = px + dx * ln, py + dy * ln
            self.wire(px, py, ex, ey)
            d = (int(round(dx)), int(round(dy)))
            if net == 'GND':
                self.pwr += 1
                self.place('power:GND', f'#PWR{self.pwr:04d}', 'GND', ex, ey, {(0, 1): 0, (1, 0): 90, (0, -1): 180, (-1, 0): 270}[d])
            else:
                self.label(net, ex, ey, d)
        extra = set(nets) - {p['num'] for p in pins}
        assert not extra, (ref, extra)

    def R(self, ref, val, x, y, a, b, fp='Resistor_SMD:R_0603_1608Metric'):
        self.place('Device:R', ref, val, x, y, 90, {'1': a, '2': b}, fp, ref_at=(x, y - 2.3), val_at=(x, y + 2.6), just='center')

    def C(self, ref, val, x, y, a, b, fp='Capacitor_SMD:C_0603_1608Metric'):
        self.place('Device:C', ref, val, x, y, 90, {'1': a, '2': b}, fp, ref_at=(x, y - 3.0), val_at=(x, y + 3.3), just='center')

    def save(self, path=None):
        open(path or self.path, 'w').write(dump(['kicad_sch'] + self.root) + '\n' if self.root[0] != 'kicad_sch' else dump(self.root) + '\n')
