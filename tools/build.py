"""Builds field_eyes_v2.kicad_pcb: footprints from the schematic netlist, nets, net classes, a rounded
2-layer outline and a grouped compact placement. Routing is done afterwards by Freerouting."""
import sys, math
import pcbnew
import netlist

OUT = sys.argv[1]
W, H, RAD = float(sys.argv[2]), float(sys.argv[3]), 4.0      # board size (mm) and corner radius
FP = '/Applications/KiCad/KiCad.app/Contents/SharedSupport/footprints/'
PRJ = '/private/tmp/claude-501/-Users-louiskwezi-Downloads-agri/5f73f21e-312d-4bb6-b6dd-0fed91601810/scratchpad/kboard/field_eyes.pretty'
mm = pcbnew.FromMM

comps, nets = netlist.load('board.net')
board = pcbnew.BOARD()
board.SetCopperLayerCount(2)

# ---------------------------------------------------------------- design rules / net classes
ds = board.GetDesignSettings()
ds.m_TrackMinWidth = mm(0.2)
ds.m_ViasMinSize = mm(0.6)
ds.m_ViasMinDrill = mm(0.3)
ds.m_MinClearance = mm(0.2)
ds.m_CopperEdgeClearance = mm(0.3)
ns = ds.m_NetSettings
default = ns.GetDefaultNetclass()
default.SetClearance(mm(0.2)); default.SetTrackWidth(mm(0.25)); default.SetViaDiameter(mm(0.6)); default.SetViaDrill(mm(0.3))

CLASSES = {
    'Power': (0.5, 0.2, ['VSYS', '/Modem/MODEM_VBAT', '/Power/SOLAR_RAW', '/Power/SOLAR_P', '/Power/CHG_D', '/Power/CHG_SW',
                          '/Power/CHG_CSP', '/Power/BATN', '/Power/PROT_D', '/Power/SENS_VIN', '/Power/BST_SW', '+12V_SENS',
                          '/Sensors & valve/VALVE_RES', '/Sensors & valve/MX_VDD', '/Sensors & valve/VALVE_A',
                          '/Sensors & valve/VALVE_B']),
    'Supply': (0.35, 0.2, ['GND', '+3V3', '+3V3_SW', '/Modem/VDD_1V8', '/Modem/SIM_VDD', '/Sensors & valve/VALVE_9V']),
    'RF': (0.6, 0.25, ['/Modem/RF_ANT', '/Modem/ANT_FEED']),
}
for cname, (w, clr, members) in CLASSES.items():
    nc = pcbnew.NETCLASS(cname)
    nc.SetTrackWidth(mm(w)); nc.SetClearance(mm(clr)); nc.SetViaDiameter(mm(0.6)); nc.SetViaDrill(mm(0.3))
    ns.SetNetclass(cname, nc)
    for m in members:
        assert m in nets, m
        ns.SetNetclassPatternAssignment(m, cname)

# ---------------------------------------------------------------- nets
netinfo = {}
for name in nets:
    ni = pcbnew.NETINFO_ITEM(board, name)
    board.Add(ni)
    netinfo[name] = ni
padnet = {}
for name, nodes in nets.items():
    for ref, pin in nodes:
        padnet[(ref, pin)] = name

# ---------------------------------------------------------------- footprints
fps = {}
for ref, c in comps.items():
    lib, name = c['fp'].split(':')
    fp = pcbnew.FootprintLoad(PRJ if lib == 'field_eyes' else FP + lib + '.pretty', name)
    assert fp is not None, c['fp']
    fp.SetReference(ref)
    fp.SetValue(c['value'])
    fp.SetFPIDAsString(c['fp'])
    fp.SetPath(pcbnew.KIID_PATH(c['sheet'] + c['tstamp']))
    if c['dnp'] and hasattr(fp, 'SetDNP'):
        fp.SetDNP(True)
    for pad in fp.Pads():
        n = padnet.get((ref, pad.GetNumber()))
        if n and not n.startswith('unconnected-'):
            pad.SetNet(netinfo[n])
    fp.Reference().SetTextSize(pcbnew.VECTOR2I(mm(0.8), mm(0.8)))
    fp.Reference().SetTextThickness(mm(0.12))
    fp.Value().SetVisible(False)
    board.Add(fp)
    fps[ref] = fp

def size(ref):
    fp = fps[ref]
    cy = fp.GetCourtyard(pcbnew.B_CrtYd if fp.IsFlipped() else pcbnew.F_CrtYd)
    bb = cy.BBox() if cy.OutlineCount() else fp.GetBoundingBox(False, False)
    return pcbnew.ToMM(bb.GetWidth()), pcbnew.ToMM(bb.GetHeight()), bb

def put(ref, x, y, rot=0, back=False):
    fp = fps[ref]
    if back and not fp.IsFlipped():
        fp.Flip(fp.GetPosition(), pcbnew.FLIP_DIRECTION_LEFT_RIGHT if hasattr(pcbnew, 'FLIP_DIRECTION_LEFT_RIGHT') else False)
    fp.SetOrientationDegrees(rot)
    fp.SetPosition(pcbnew.VECTOR2I(mm(x), mm(y)))
    # move so the courtyard centre lands on (x, y)
    _, _, bb = size(ref)
    c = bb.GetCenter()
    fp.Move(pcbnew.VECTOR2I(mm(x) - c.x, mm(y) - c.y))

placed = set()
def pack(region, refs, gap=0.5, rot=0):
    """shelf-pack refs (courtyard boxes) into region (x0, y0, x1, y1), left to right, top to bottom"""
    x0, y0, x1, y1 = region
    x, y, row_h = x0, y0, 0
    for r in refs:
        fps[r].SetOrientationDegrees(rot)
        w, h, _ = size(r)
        if x + w > x1 + 1e-6:
            x, y, row_h = x0, y + row_h + gap, 0
        put(r, x + w / 2, y + h / 2, rot)
        placed.add(r)
        x += w + gap
        row_h = max(row_h, h)
    if y + row_h > y1 + 1e-6:
        print(f'  ! region {region} overflows to y={y + row_h:.1f}: {refs[-1]}')

def at(ref, x, y, rot=0, back=False):
    put(ref, x, y, rot, back)
    placed.add(ref)

# ---------------------------------------------------------------- outline (rounded rectangle)
def edge_line(a, b):
    s = pcbnew.PCB_SHAPE(board, pcbnew.SHAPE_T_SEGMENT)
    s.SetStart(pcbnew.VECTOR2I(mm(a[0]), mm(a[1]))); s.SetEnd(pcbnew.VECTOR2I(mm(b[0]), mm(b[1])))
    s.SetLayer(pcbnew.Edge_Cuts); s.SetWidth(mm(0.1)); board.Add(s)

def edge_arc(c, start_deg):
    s = pcbnew.PCB_SHAPE(board, pcbnew.SHAPE_T_ARC)
    a0 = math.radians(start_deg); a1 = math.radians(start_deg + 45); a2 = math.radians(start_deg + 90)
    p = lambda a: pcbnew.VECTOR2I(mm(c[0] + RAD * math.cos(a)), mm(c[1] + RAD * math.sin(a)))
    s.SetArcGeometry(p(a0), p(a1), p(a2))
    s.SetLayer(pcbnew.Edge_Cuts); s.SetWidth(mm(0.1)); board.Add(s)

edge_line((RAD, 0), (W - RAD, 0)); edge_line((W, RAD), (W, H - RAD))
edge_line((W - RAD, H), (RAD, H)); edge_line((0, H - RAD), (0, RAD))
edge_arc((W - RAD, RAD), 270); edge_arc((W - RAD, H - RAD), 0); edge_arc((RAD, H - RAD), 90); edge_arc((RAD, RAD), 180)

# ---------------------------------------------------------------- placement
L = lambda *refs: [r for r in refs if r in fps]

# 18650 holder on the back under the top half; NTC on the back just below the cell
at('BT101', 48, 13.5, 0, back=True)
at('TH101', 58, 26.4, 0, back=True)

# ESP32: antenna overhangs the top edge (module antenna boundary on y = 0)
esp = fps['U201']; esp.SetOrientationDegrees(0); esp.SetPosition(pcbnew.VECTOR2I(mm(17), mm(9.6))); placed.add('U201')

# modem rotated so RF + VBAT face the right edge, UART/PWRKEY face up, SIM/USB face left
mdm = fps['U301']; mdm.SetOrientationDegrees(270); mdm.SetPosition(pcbnew.VECTOR2I(mm(W - 22), mm(17))); placed.add('U301')
# antenna chain: RF pad (W-9, 17) -> R317 -> U.FL at the edge; matching caps either side
at('R317', W - 7.4, 17, 0); at('C311', W - 8.0, 14.6, 90); at('C312', W - 5.4, 20.2, 90)
at('J301', W - 2.9, 17, 90)

# modem VBAT network under the modem's VBAT corner
pack((W - 33, 30.3, W - 1.5, 37), L('C301', 'C302', 'FB301', 'C303', 'C304', 'C305', 'C306', 'D301'), gap=0.3)
at('J303', 51, 35.9, 90)

# SIM holder left of the modem, its ESD/resistors above it
at('J302', 53.9, 22.2, 90)
pack((46.8, 1.0, 61.5, 14.5), L('U302', 'R314', 'R315', 'R316', 'C310', 'TP301'), gap=0.3)

# modem control / level shifting between the ESP32 and the SIM area
pack((27, 1.0, 46.5, 29.5), L('Q301', 'R301', 'R302', 'Q302', 'R303', 'R304', 'Q303', 'R305', 'C307', 'R306',
                            'Q304', 'R307', 'C308', 'R308', 'Q305', 'R309', 'R310', 'Q306', 'R311', 'R312',
                            'R313', 'D302', 'C309'), gap=0.3)

# ESP32 support below the module (keep clear of the holder peg at (11.9, 21.5))
pack((14.2, 20.3, 26.5, 38), L('C202', 'C203', 'C204', 'R201', 'C201', 'R202', 'Q201', 'Q202', 'R203', 'R204'), gap=0.3)
at('SW201', 5.6, 24.9, 90); at('SW202', 5.6, 33.9, 90)

# left edge: programming, OLED and DHT22 headers
at('J201', 3.4, 48.2, 0); at('J202', 7.6, 46.0, 0); at('J203', 11.8, 44.8, 0)
pack((6.0, 52.6, 14.5, 58), L('R205', 'R206', 'R207'), gap=0.3)

# protection, LDO, service header (row under the modem-control block)
pack((27, 30.3, W - 34, 38), L('U102', 'Q104', 'U103', 'R109', 'C106', 'R110', 'R111', 'R112', 'C107', 'R113',
                                 'C108', 'C111'), gap=0.3)

# charger (left middle), switches + boost (centre), valve driver (right)
pack((14.5, 38.5, 42.3, 54), L('L101', 'U101', 'D101', 'D102', 'Q101', 'Q102', 'R103', 'C101', 'C105', 'C102', 'C103',
                               'R101', 'R104', 'C104', 'R105', 'R106', 'R107', 'R108'), gap=0.3)
pack((42.8, 38.5, 68.5, 54), L('L102', 'U104', 'D103', 'C114', 'C113', 'Q105', 'Q106', 'Q107', 'Q108', 'R118', 'R119',
                                 'R114', 'R115', 'R116', 'R117', 'R120', 'C109', 'C110', 'C112'), gap=0.3)
at('Q103', 31, 52.6, 0)
pack((69, 38.5, W - 1.5, 54), L('U403', 'U404', 'D403', 'JP401', 'C404', 'C405', 'C406', 'C407', 'R421', 'R422'), gap=0.3)

# RS485 row and the screw terminals on the bottom edge
pack((14.5, 54.4, 72.5, 62.8), L('U401', 'U402', 'Q401', 'Q402', 'D401', 'D402', 'C401', 'C402', 'R401', 'R402', 'R403',
                               'R404', 'R405', 'R406', 'R407', 'R411', 'R412', 'R413', 'R414', 'R415', 'R416', 'R417'), gap=0.3)
at('J101', 13.6, H - 4.6, 0); at('J401', 27.5, H - 4.6, 0); at('J402', 44.5, H - 4.6, 0); at('J403', 58.5, H - 4.6, 0)
at('C403', W - 15.5, H - 7.8, 0)

# mounting holes in the four rounded corners
for ref, (x, y) in zip(['H201', 'H202', 'H203', 'H204'], [(3.6, 3.6), (W - 3.6, 3.6), (3.6, H - 3.6), (W - 3.6, H - 3.6)]):
    at(ref, x, y)

# ---------------------------------------------------------------- checks
def boxes(side_back):
    out = []
    for r, fp in fps.items():
        if fp.IsFlipped() != side_back or r == 'U201':
            continue
        w, h, bb = size(r)
        if r == 'U301':  # imported footprint has no proper courtyard: use the 24 x 24 body
            c = fp.GetPosition(); bb = pcbnew.BOX2I(pcbnew.VECTOR2I(c.x - mm(12.6), c.y - mm(12.6)), pcbnew.VECTOR2I(mm(25.2), mm(25.2)))
        out.append((r, pcbnew.ToMM(bb.GetLeft()), pcbnew.ToMM(bb.GetTop()), pcbnew.ToMM(bb.GetRight()), pcbnew.ToMM(bb.GetBottom())))
    e = fps['U201'].GetPosition()
    out.append(('U201', pcbnew.ToMM(e.x) - 9.6, 0, pcbnew.ToMM(e.x) + 9.6, pcbnew.ToMM(e.y) + 10.6))
    return out
top = boxes(False)
over = []
for i in range(len(top)):
    for j in range(i + 1, len(top)):
        a, b2 = top[i], top[j]
        ox = min(a[3], b2[3]) - max(a[1], b2[1]); oy = min(a[4], b2[4]) - max(a[2], b2[2])
        if ox > 0.05 and oy > 0.05:
            over.append((a[0], b2[0], round(ox, 1), round(oy, 1)))
print('top courtyard overlaps:', over)
outside = [b2[0] for b2 in top if b2[1] < -0.01 or b2[2] < -0.01 or b2[3] > W + 0.01 or b2[4] > H + 0.01]
print('outside board:', outside)
for pad in fps['BT101'].Pads():
    if pad.GetAttribute() == pcbnew.PAD_ATTRIB_NPTH:
        p = pad.GetPosition(); rr = pcbnew.ToMM(pad.GetDrillSize().x) / 2 + 0.4
        hit = [b2[0] for b2 in top if b2[1] - rr < pcbnew.ToMM(p.x) < b2[3] + rr and b2[2] - rr < pcbnew.ToMM(p.y) < b2[4] + rr]
        print(f'holder peg at ({pcbnew.ToMM(p.x):.1f},{pcbnew.ToMM(p.y):.1f}) near:', hit)

missing = [r for r in fps if r not in placed]
if missing:
    print('NOT PLACED:', missing)

board.Save(OUT)
print('saved', OUT, f'{W}x{H} mm')
