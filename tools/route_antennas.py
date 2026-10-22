"""Routes the two antenna lines (GPS and LTE): 3 mm 50-ohm microstrip (1.6 mm FR4, ground plane on the bottom layer) that steps down to the
pad widths, ground vias at the U.FL ground pads and the matching-cap pads, and the bottom ground plane.
Track ends are round, so every step to a wider track starts far enough from the neighbouring pads (half the width + clearance)."""
import sys, math
import pcbnew
pcb, out = sys.argv[1], sys.argv[2]
mm, tomm = pcbnew.FromMM, pcbnew.ToMM
board = pcbnew.LoadBoard(pcb)
bb = board.GetBoardEdgesBoundingBox()
X0, Y0 = tomm(bb.GetLeft()) + 0.05, tomm(bb.GetTop()) + 0.05
W, H = tomm(bb.GetWidth()) - 0.1, tomm(bb.GetHeight()) - 0.1
fps = {f.GetReference(): f for f in board.GetFootprints()}
V = lambda x, y: pcbnew.VECTOR2I(mm(X0 + x), mm(Y0 + y))

def pad(ref, num, idx=0):
    q = [p for p in fps[ref].Pads() if p.GetNumber() == num][idx].GetPosition()
    return (tomm(q.x) - X0, tomm(q.y) - Y0)

def move(ref, x, y, rot):
    f = fps[ref]; f.SetOrientationDegrees(rot); f.SetPosition(V(x, y))

# re-runnable: phase 1 drops what an earlier run put on these nets (and the planes), saves, and restarts the script
# for phase 2, because pcbnew's footprint handles stop working after items are removed
RF_NETS = ('/GPS_ANT', '/GPS_SIG', '/GPS_BIAS', '/RF_ANT', '/ANT_FEED')
if '--clean-done' not in sys.argv:
    doomed = [t for t in board.GetTracks() if t.GetNetname() in RF_NETS or (t.GetClass() == 'PCB_VIA' and t.GetNetname() == 'GND')]
    doomed += [z for z in board.Zones() if z.GetZoneName() in ('GND_BOTTOM', 'GND_TOP') or z.GetZoneName().startswith('KO_') or (z.GetLayer() == pcbnew.B_Cu and z.GetNetname() == 'GND')]
    for t in doomed:
        board.Remove(t)
    board.Save(out)
    import os; os.execv(sys.executable, [sys.executable, sys.argv[0], out, out, '--clean-done'])

# ------------------------------------------------------------------ parts on the lines
move('C313', 81.2, 9.2, 90)          # GPS: DC-block capacitor just below the connector
move('L301', 75.2, 10.5, 270)        # GPS bias inductor and resistor on the west side, below the ESP32 antenna zone
move('R318', 75.2, 14.0, 270)
move('J301', 113.33, 25.9, 0)        # LTE connector turned so that its centre pin faces the modem
move('R317', 110.0, 25.8, 0)         # LTE series resistor in line; the two unfitted matching capacitors hang off the line
move('C311', 108.9, 24.12, 90)
move('C312', 111.2, 24.97, 90)

def track(netname, pts, widths):
    net = board.FindNet(netname)
    for (a, b), w in zip(zip(pts, pts[1:]), widths):
        t = pcbnew.PCB_TRACK(board)
        t.SetStart(V(*a)); t.SetEnd(V(*b)); t.SetWidth(mm(w)); t.SetLayer(pcbnew.F_Cu); t.SetNet(net)
        board.Add(t)

def via(x, y):
    v = pcbnew.PCB_VIA(board)
    v.SetPosition(V(x, y)); v.SetWidth(mm(0.6)); v.SetDrill(mm(0.3)); v.SetNet(board.FindNet('GND'))
    v.SetViaType(pcbnew.VIATYPE_THROUGH); v.SetLayerPair(pcbnew.F_Cu, pcbnew.B_Cu)
    board.Add(v)

def ground(ref, num, idx, dx, dy, stub=True):
    """via beside a ground pad; the stub track is only needed where the top pour cannot reach the pad (inside the RF clearance window)"""
    gx, gy = pad(ref, num, idx)
    via(gx + dx, gy + dy)
    if stub:
        track('GND', [(gx, gy), (gx + dx, gy + dy)], [0.5])

# ================================================================ GPS
gp = pad('U301', 'P$90')                        # modem GPS pad, on the modem's left edge
c1, c2 = pad('C313', '1'), pad('C313', '2')     # c1 = modem side (GPS_ANT), c2 = connector side (GPS_SIG)
j1 = pad('J304', '1')
y0 = gp[1]
xv = 78.8                                       # centre of the 3.0 mm vertical run
track('/GPS_ANT',
      [gp, (80.0, y0), (79.5, y0), (xv, y0), (xv, c1[1] + 1.7), (79.8, c1[1] + 1.25), (80.6, c1[1] + 0.85), (c1[0], c1[1] + 0.85), c1],
      [0.64, 1.4, 2.2, 3.0, 2.2, 1.2, 0.6, 0.6])
track('/GPS_SIG', [c2, (c2[0], c2[1] - 0.9), j1], [0.6, 1.0])
# bias branch: from the capacitor pad west at y = 9.0 (just below the antenna zone) to the inductor
lp = pad('L301', '1')
track('/GPS_SIG', [c2, (c2[0] - 0.6, 9.0), (lp[0], 9.0), lp], [0.3, 0.3, 0.3])
track('/GPS_BIAS', [pad('L301', '2'), pad('R318', '1')], [0.3])
ground('J304', '2', 0, -1.0, -1.6, stub=False)
ground('J304', '2', 1, 1.0, -1.6, stub=False)

# ================================================================ LTE
lt = pad('U301', 'P$60')                        # modem RF pad, on the modem's right edge
r1, r2 = pad('R317', '1'), pad('R317', '2')
f1 = pad('J301', '1')
y = lt[1]
track('/RF_ANT', [lt, (107.3, y), (107.9, y), (108.4, y), (108.8, y), (109.2, y), r1],
      [0.64, 1.4, 2.2, 2.2, 1.4, 0.64])      # only 3 mm to the resistor: 2.2 mm (about 60 ohm) is the widest that fits
track('/RF_ANT', [(108.9, y), pad('C311', '1')], [0.5])
track('/ANT_FEED', [r2, (r2[0] + 0.5, y), (f1[0] - 0.4, f1[1]), f1], [0.64, 1.0, 1.0])
track('/ANT_FEED', [(111.2, y), pad('C312', '1')], [0.4])
ground('J301', '2', 0, 0.0, -1.8, stub=False)
ground('J301', '2', 1, 0.0, 1.8, stub=False)
ground('C311', '2', 0, 0.0, -1.2)
ground('C312', '2', 0, 0.0, -1.2)

# ================================================================ ground planes on both layers (the return path for both lines)
LS = lambda *l: (lambda s: [s.AddLayer(x) for x in l] and s)(pcbnew.LSET())

def rect(z, x0, y0, x1, y1):
    ol = z.Outline(); ol.NewOutline()
    for x, yy in ((x0, y0), (x1, y0), (x1, y1), (x0, y1)):
        ol.Append(mm(X0 + x), mm(Y0 + yy))

def keepout(name, layers, box):
    """no copper pour in this box (tracks, vias and pads are still allowed)"""
    z = pcbnew.ZONE(board); z.SetIsRuleArea(True); z.SetZoneName(name); z.SetLayerSet(LS(*layers))
    z.SetDoNotAllowCopperPour(True); z.SetDoNotAllowTracks(False); z.SetDoNotAllowVias(False)
    z.SetDoNotAllowPads(False); z.SetDoNotAllowFootprints(False)
    rect(z, *box); board.Add(z)

def plane(layer, name, connect=pcbnew.ZONE_CONNECTION_THERMAL):
    z = pcbnew.ZONE(board); z.SetLayer(layer); z.SetNet(board.FindNet('GND')); z.SetZoneName(name)
    z.SetLocalClearance(mm(0.3)); z.SetMinThickness(mm(0.25))
    z.SetPadConnection(connect)
    z.SetThermalReliefGap(mm(0.4)); z.SetThermalReliefSpokeWidth(mm(0.5))
    z.SetIslandRemovalMode(pcbnew.ISLAND_REMOVAL_MODE_ALWAYS)
    rect(z, 0, 0, W, H); board.Add(z)

# the ESP32 footprint carries its own no-copper keep-out for the antenna end (x 30.2..78.2, y 0..9.1): the pours stay out of it
ESP_KO = (30.2, 0.0, 78.2, 9.4)
# SIMCom guide 4.2: keep the 50 ohm line free of nearby ground on its own layer (that would lower the impedance): 1 mm each side of the line
keepout('KO_RF_LTE', (pcbnew.F_Cu,), (106.4, y - 2.5, 112.0, y + 2.5))
keepout('KO_RF_GPS', (pcbnew.F_Cu,), (76.3, 8.3, 82.6, gp[1] + 1.5 + 1.0))
plane(pcbnew.B_Cu, 'GND_BOTTOM')
plane(pcbnew.F_Cu, 'GND_TOP', pcbnew.ZONE_CONNECTION_FULL)

# ---- stitching vias: tie the two planes together along the board edge and along both sides of the RF lines
def free(x, y):
    p = V(x, y); rv = 0.3 + 0.35
    for f in board.GetFootprints():
        if f.GetReference() == 'J302':          # the SIM tray has copper shapes that are not pads: keep clear of its whole outline
            bx = f.GetBoundingBox(False); m = mm(0.8)
            if bx.GetLeft() - m <= p.x <= bx.GetRight() + m and bx.GetTop() - m <= p.y <= bx.GetBottom() + m: return False
        for pd in f.Pads():
            if pd.HitTest(p, mm(rv + 0.15)): return False
    for t in board.GetTracks():
        if t.HitTest(p, mm(rv)): return False
    if ESP_KO[0] <= x <= ESP_KO[2] and ESP_KO[1] <= y <= ESP_KO[3]: return False
    return True

def outside_corner(x, y, m=1.0, rad=4.0):
    cx = min(max(x, rad), W - rad); cy = min(max(y, rad), H - rad)
    return math.hypot(x - cx, y - cy) <= rad - m

n = 0
def stitch(x, y):
    global n
    if 0.8 <= x <= W - 0.8 and 0.8 <= y <= H - 0.8 and outside_corner(x, y) and free(x, y):
        via(x, y); n += 1

step = 6.0
x = 5.0
while x < W - 4.0:
    stitch(x, 1.2); stitch(x, H - 1.2); x += step
yy = 5.0
while yy < H - 4.0:
    stitch(1.2, yy); stitch(W - 1.2, yy); yy += step
# along the RF lines
for xx in (107.0, 109.0, 111.0): stitch(xx, y - 3.2); stitch(xx, y + 3.2)
for yv in (9.5, 12.0, 14.5, 17.0): stitch(75.4, yv) if False else None
for yv in (10.0, 12.5, 15.0, 17.5): stitch(75.9, yv); stitch(83.2, yv) if yv > 17 else None
board.Save(out)   # unfilled copy first so a fill problem cannot lose the work
pcbnew.ZONE_FILLER(board).Fill(board.Zones())
board.Save(out)
print('saved', out, '| tracks', len([t for t in board.GetTracks() if t.GetClass() == 'PCB_TRACK']), '| vias', len([t for t in board.GetTracks() if t.GetClass() == 'PCB_VIA']), '| stitching vias', n)
