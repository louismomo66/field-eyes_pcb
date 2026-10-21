"""Re-places the board like the old design (security.brd): same positions for the ESP32, modem, SIM tray, antenna and sensor
connectors, with the board widened on the left to make room for the new power / valve circuits. Positions only: nets are untouched."""
import sys, math
import pcbnew
pcb, out = sys.argv[1], sys.argv[2]
DW = float(sys.argv[3]) if len(sys.argv) > 3 else 28.0       # extra width on the left (mm)
H = float(sys.argv[4]) if len(sys.argv) > 4 else 60.0
DH = H - 59.9                                                  # extra height, added under the old middle of the board
RAD = 4.0
mm, tomm = pcbnew.FromMM, pcbnew.ToMM
board = pcbnew.LoadBoard(pcb)
fps = {f.GetReference(): f for f in board.GetFootprints()}
bb = board.GetBoardEdgesBoundingBox()
X0, Y0 = tomm(bb.GetLeft()) + 0.05, tomm(bb.GetTop()) + 0.05
W = 100.3 + DW

def courtyard(fp):
    cy = fp.GetCourtyard(pcbnew.B_CrtYd if fp.IsFlipped() else pcbnew.F_CrtYd)
    return cy.BBox() if cy.OutlineCount() else fp.GetBoundingBox(False, False)

def put(ref, x, y, rot=0, origin=False):
    """courtyard centre (or the footprint origin) at board coordinates (x, y)"""
    fp = fps[ref]
    fp.SetOrientationDegrees(rot)
    fp.SetPosition(pcbnew.VECTOR2I(mm(X0 + x), mm(Y0 + y)))
    if not origin:
        c = courtyard(fp).GetCenter()
        fp.Move(pcbnew.VECTOR2I(mm(X0 + x) - c.x, mm(Y0 + y) - c.y))
    placed.add(ref)

def size(ref):
    b = courtyard(fps[ref])
    return tomm(b.GetWidth()), tomm(b.GetHeight())

placed = set()
def pack(region, refs, gap=0.3, rot=0):
    x0, y0, x1, y1 = region
    x, y, rowh = x0, y0, 0
    for r in refs:
        fps[r].SetOrientationDegrees(rot)
        w, h = size(r)
        if x + w > x1 + 1e-6:
            x, y, rowh = x0, y + rowh + gap, 0
        put(r, x + w / 2, y + h / 2, rot)
        x += w + gap
        rowh = max(rowh, h)
    if y + rowh > y1 + 1e-6:
        print(f'  ! region {region} overflows to y={y + rowh:.1f} at {refs[-1]}')

# parts that sat on the old board's bottom edge move down with it, so the bottom row stays on the (now lower) edge
BOTTOM = {'J302', 'X1', 'X2', 'X4', 'U401', 'U402', 'Q401', 'Q402', 'U302', 'R314', 'R315', 'R316', 'C310', 'TP301', 'J403'}
oy_of = lambda ref, oy: oy + (DH if ref in BOTTOM else 0.0)
# ------------------------------------------------------------------ the old design's positions (old x + DW)
HARD = {   # parts that sit exactly where they did on the old board: ref: (old x, old y, rotation)
    'SV1': (50.6, 4.8, 0), 'J301': (95.2, 25.9, 180),
    'J302': (81.4, 51.8, 0), 'X2': (31.2, 55.4, 0), 'X1': (45.4, 55.3, 0), 'X4': (59.6, 55.3, 0),
}
for ref, (ox, oy, rot) in HARD.items():
    put(ref, ox + DW, oy_of(ref, oy), rot)
put('U201', 36.2 + DW, 2.3 + 15.8, 0, origin=True)      # ESP32: body top 2.3 mm from the edge, as before
put('U301', 75.7 + DW, 25.8, 270, origin=True)
for ref, (x, y) in zip(('H201', 'H202', 'H203', 'H204'), ((3.6, 3.6), (W - 3.6, 3.6), (3.6, H - 3.6), (W - 3.6, H - 3.6))):
    put(ref, x, y)
# GPS antenna: a clear corridor for the 50 ohm line from the modem's GPS pad (on its left edge) north to the U.FL on the top edge.
# The U.FL sits just outside the ESP32 antenna keep-out; C313 is in line, L301/R318 (the bias) hang off to the side.
GPS_PAD = (75.7 + DW - 12.0, 25.8 - 10.0)
GPS_KEEPOUT = (GPS_PAD[0] - 9.7, 8.6, GPS_PAD[0] + 3.2, GPS_PAD[1] + 3.0)      # nothing but the GPS parts may sit here (room for the 3 mm track to bend)
put('C313', GPS_PAD[0] - 2.6, 13.8, 90)
put('L301', GPS_PAD[0] - 6.0, 14.8, 90)
put('R318', GPS_PAD[0] - 6.0, 11.2, 90)
best = None                                                    # turn J304 so that its signal pad faces the modem pad
for rot in (0, 90, 180, 270):
    put('J304', GPS_PAD[0] - 0.5, 5.6, rot)
    sig = [pd for pd in fps['J304'].Pads() if pd.GetNumber() == '1'][0].GetPosition()
    score = (tomm(sig.y) - Y0) * 10 - abs(tomm(sig.x) - X0 - (GPS_PAD[0] - 0.5))
    if best is None or score > best[0]:
        best = (score, rot)
put('J304', GPS_PAD[0] - 0.5, 5.6, best[1])
put('BT101', W / 2, 34.0, 0)                           # battery holder on the back
put('TH101', W / 2 + 12, 34.0, 0)

def box(ref):
    fp = fps[ref]
    if ref == 'U301':
        p = fp.GetPosition(); return (tomm(p.x) - 12.6 - X0, tomm(p.y) - 12.6 - Y0, tomm(p.x) + 12.6 - X0, tomm(p.y) + 12.6 - Y0)
    if ref == 'U201':   # module body; its antenna end is a keep-out with no copper, so parts may not sit in it either
        p = fp.GetPosition(); return (tomm(p.x) - 9.4 - X0, 0.0, tomm(p.x) + 9.4 - X0, tomm(p.y) + 10.0 - Y0)
    b = courtyard(fp)
    return (tomm(b.GetLeft()) - X0, tomm(b.GetTop()) - Y0, tomm(b.GetRight()) - X0, tomm(b.GetBottom()) - Y0)

def pegs():
    u = fps['U201'].GetPosition()
    out = [list(GPS_KEEPOUT), [tomm(u.x) - X0 - 24.0, 0.0, tomm(u.x) - X0 + 24.0, tomm(u.y) - Y0 - 9.0]]
    for pad in fps['BT101'].Pads():
        if pad.GetAttribute() == pcbnew.PAD_ATTRIB_NPTH:
            q = pad.GetPosition(); r = tomm(pad.GetDrillSize().x) / 2 + 0.7
            out.append((tomm(q.x) - X0 - r, tomm(q.y) - Y0 - r, tomm(q.x) - X0 + r, tomm(q.y) - Y0 + r))
    return out

def autoplace(ref, anchor, rot=0, margin=0.3, edge=0.9):
    """nearest free spot to the anchor (board coordinates), spiralling outwards"""
    fps[ref].SetOrientationDegrees(rot)
    w, h = size(ref)
    occ = [box(r) for r in placed if not fps[r].IsFlipped()] + pegs()
    for k in range(20000):
        rr = 0.3 * math.sqrt(k); a = k * 2.399963
        cx, cy = anchor[0] + rr * math.cos(a), anchor[1] + rr * math.sin(a)
        c = (cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2)
        if c[0] < edge or c[1] < edge or c[2] > W - edge or c[3] > H - edge:
            continue
        if all(c[2] + margin <= o[0] or o[2] + margin <= c[0] or c[3] + margin <= o[1] or o[3] + margin <= c[1] for o in occ):
            put(ref, cx, cy, rot); return (cx, cy)
    print('  ! no free spot for', ref); return None

def group(refs, anchor, rot=0):
    refs = [r for r in refs if r in fps and r not in placed]
    refs.sort(key=lambda r: -(size(r)[0] * size(r)[1]))
    for r in refs:
        autoplace(r, anchor, rot)

# parts that had a counterpart on the old board stay near the old position (old x + DW); the rest go to their circuit's area
NEAR = {
    'X3': (54.8, 27.5, 90),
    'Q304': (66.7, 9.3, 180), 'Q302': (71.8, 9.3, 180), 'Q303': (78.0, 9.4, 0),
    'R319': (93.1, 11.1, 0), 'R313': (94.2, 14.6, 0),
    'C301': (92.0, 40.9, 90), 'D302': (96.1, 30.6, 180), 'Q306': (93.3, 33.2, 90), 'R312': (95.6, 33.1, 0), 'R311': (98.7, 33.1, 0),
    'FB301': (96.1, 41.7, 270), 'C302': (95.9, 37.6, 270), 'C303': (98.1, 37.6, 270), 'C304': (98.4, 41.7, 270), 'D301': (95.2, 45.6, 0),
    'C305': (91.5, 37.0, 0), 'C306': (91.5, 35.0, 0),
    'R320': (81.6, 40.7, 270), 'R321': (84.3, 40.7, 270),
    'U302': (71.3, 50.4, 0), 'R315': (67.0, 46.5, 90), 'R314': (69.5, 46.6, 90), 'R316': (71.8, 46.5, 90), 'C310': (71.1, 54.1, 0),
    'R317': (91.6, 25.9, 0), 'C311': (91.0, 22.8, 90), 'C312': (91.0, 29.0, 90), 'TP301': (66.0, 52.5, 0),
    'U401': (27.6, 47.4, 0), 'U402': (46.5, 47.1, 0), 'Q401': (28.5, 42.6, 0), 'Q402': (45.8, 43.6, 0),
}
# big or fussy first
for ref in ('X3', 'C301', 'U401', 'U402', 'U302', 'D302', 'Q306', 'Q304', 'Q302', 'Q303', 'Q401', 'Q402'):
    ox, oy, rot = NEAR[ref]; autoplace(ref, (ox + DW, oy_of(ref, oy)), rot)
for ref, (ox, oy, rot) in NEAR.items():
    if ref not in placed:
        autoplace(ref, (ox + DW, oy_of(ref, oy)), rot)
autoplace('J303', (DW + 99.0, 56.0 + DH), 90)
for _r, _y in (('SW201', 10.0), ('SW202', 20.5)):
    if _r in fps: autoplace(_r, (DW + 14.0, _y), 90)
autoplace('J101', (5.5, 22.0), 90); autoplace('J403', (14.0, H - 6.0), 0); autoplace('C403', (28.0, H - 10.0), 0)
group(['Q301', 'Q305', 'R301', 'R302', 'R303', 'R304', 'R305', 'R306', 'R307', 'R308', 'R309', 'R310', 'C307', 'C308', 'C309'], (DW + 76.0, 7.0))
group(['C202', 'C203', 'C204', 'R201', 'C201', 'R202', 'Q201', 'Q202', 'R203', 'R204'], (DW + 36.0, 31.5))
group(['R205', 'R206', 'R207'], (DW + 49.0, 22.0))
group(['U101', 'L101', 'D101', 'D102', 'Q101', 'Q102', 'R103', 'C101', 'C105', 'C102', 'C103', 'R101', 'R104', 'C104', 'R105', 'R106',
       'R107', 'R108', 'Q103'], (11.0, 11.0))
group(['U104', 'L102', 'D103', 'C114', 'C113', 'Q105', 'Q106', 'Q107', 'Q108', 'R118', 'R119', 'R114', 'R115', 'R116', 'R117', 'R120',
       'C109', 'C110', 'C112', 'U405', 'C408', 'C409'], (DW + 6.0, 14.0))
group(['U102', 'Q104', 'U103', 'R109', 'C106', 'R110', 'R111', 'R112', 'C107', 'R113', 'C108', 'C111'], (12.0, 32.0))
group(['U403', 'U404', 'D403', 'JP401', 'C404', 'C405', 'C406', 'C407', 'R421', 'R422'], (24.0, H - 14.0))
group(['R401', 'R402', 'R403', 'R404', 'R405', 'R406', 'R407', 'R411', 'R412', 'R413', 'R414', 'R415', 'R416', 'R417', 'R423', 'R424',
       'R425', 'R426', 'C401', 'C402', 'D401', 'D402'], (DW + 20.0, 42.0 + DH))

# ------------------------------------------------------------------ checks
missing = [r for r in fps if r not in placed]
print('not placed:', missing)
tops = [(r, box(r)) for r in fps if not fps[r].IsFlipped()]
bad = []
for i in range(len(tops)):
    for j in range(i + 1, len(tops)):
        a, b = tops[i][1], tops[j][1]
        if min(a[2], b[2]) - max(a[0], b[0]) > 0.05 and min(a[3], b[3]) - max(a[1], b[1]) > 0.05:
            bad.append((tops[i][0], tops[j][0]))
print('overlaps:', bad)
print('outside the board:', [r for r, b in tops if b[0] < -0.01 or b[2] > W + 0.01 or b[3] > H + 0.01 or (b[1] < -0.01 and r != 'U201')])
# ------------------------------------------------------------------ outline: rounded rectangle
for d in list(board.GetDrawings()):
    if d.GetLayer() == pcbnew.Edge_Cuts:
        board.Remove(d)
def line(a, b):
    s = pcbnew.PCB_SHAPE(board, pcbnew.SHAPE_T_SEGMENT)
    s.SetStart(pcbnew.VECTOR2I(mm(X0 + a[0]), mm(Y0 + a[1]))); s.SetEnd(pcbnew.VECTOR2I(mm(X0 + b[0]), mm(Y0 + b[1])))
    s.SetLayer(pcbnew.Edge_Cuts); s.SetWidth(mm(0.1)); board.Add(s)
def arc(c, start):
    s = pcbnew.PCB_SHAPE(board, pcbnew.SHAPE_T_ARC)
    pt = lambda a: pcbnew.VECTOR2I(mm(X0 + c[0] + RAD * math.cos(math.radians(a))), mm(Y0 + c[1] + RAD * math.sin(math.radians(a))))
    s.SetArcGeometry(pt(start), pt(start + 45), pt(start + 90))
    s.SetLayer(pcbnew.Edge_Cuts); s.SetWidth(mm(0.1)); board.Add(s)
line((RAD, 0), (W - RAD, 0)); line((W, RAD), (W, H - RAD)); line((W - RAD, H), (RAD, H)); line((0, H - RAD), (0, RAD))
arc((W - RAD, RAD), 270); arc((W - RAD, H - RAD), 0); arc((RAD, H - RAD), 90); arc((RAD, RAD), 180)

board.Save(out)
print(f'saved {out}: board {W:.1f} x {H:.1f} mm')
