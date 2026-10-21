"""Brings field_eyes_v2.kicad_pcb in line with the schematic netlist without disturbing the existing placement:
removes footprints that are gone, adds new ones in free spots, re-applies every pad's net, updates values."""
import sys, os, math
import pcbnew
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import netlist

pcb, net_path, out = sys.argv[1], sys.argv[2], sys.argv[3]
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FPLIB = '/Applications/KiCad/KiCad.app/Contents/SharedSupport/footprints/'
PRJ = os.path.join(HERE, 'field_eyes.pretty')
mm, tomm = pcbnew.FromMM, pcbnew.ToMM

comps, nets = netlist.load(net_path)
board = pcbnew.LoadBoard(pcb)
have = {f.GetReference(): f for f in board.GetFootprints()}

# nets
known = {str(n.GetNetname()): n for n in board.GetNetInfo().NetsByNetcode().values()}
for name in nets:
    if name not in known:
        ni = pcbnew.NETINFO_ITEM(board, name); board.Add(ni); known[name] = ni
# footprints that are no longer in the schematic
for ref in sorted(set(have) - set(comps)):
    board.Remove(have[ref]); print('removed', ref)
    del have[ref]

padnet = {(r, p): n for n, nodes in nets.items() for r, p in nodes}

def load_fp(fpid):
    lib, name = fpid.split(':')
    fp = pcbnew.FootprintLoad(PRJ if lib == 'field_eyes' else FPLIB + lib + '.pretty', name)
    assert fp is not None, fpid
    return fp

new = []
for ref, c in comps.items():
    fp = have.get(ref)
    if fp is None:
        fp = load_fp(c['fp'])
        fp.SetReference(ref)
        fp.SetFPIDAsString(c['fp'])
        fp.Reference().SetTextSize(pcbnew.VECTOR2I(mm(0.8), mm(0.8)))
        fp.Reference().SetTextThickness(mm(0.12))
        fp.Value().SetVisible(False)
        board.Add(fp); have[ref] = fp; new.append(ref)
    fp.SetValue(c['value'])
    fp.SetPath(pcbnew.KIID_PATH(c['sheet'] + c['tstamp']))
    for pad in fp.Pads():
        n = padnet.get((ref, pad.GetNumber()))
        if n and not n.startswith('unconnected-'):
            pad.SetNet(known[n])
        else:
            pad.SetNetCode(0)

# ---------------------------------------------------------------- placement of the new footprints
W = H = None
bb = board.GetBoardEdgesBoundingBox()
W, H = tomm(bb.GetWidth()), tomm(bb.GetHeight())
x0, y0 = tomm(bb.GetLeft()), tomm(bb.GetTop())

def box(fp):
    ref = fp.GetReference()
    p = fp.GetPosition()
    if ref == 'U301':    # the imported modem footprint has no real courtyard: use its 24 x 24 body
        return (tomm(p.x) - 12.6, tomm(p.y) - 12.6, tomm(p.x) + 12.6, tomm(p.y) + 12.6)
    if ref == 'U201':    # module plus its antenna end, which hangs over the board edge
        return (tomm(p.x) - 9.6, y0, tomm(p.x) + 9.6, tomm(p.y) + 10.6)
    cy = fp.GetCourtyard(pcbnew.B_CrtYd if fp.IsFlipped() else pcbnew.F_CrtYd)
    b = cy.BBox() if cy.OutlineCount() else fp.GetBoundingBox(False, False)
    return (tomm(b.GetLeft()), tomm(b.GetTop()), tomm(b.GetRight()), tomm(b.GetBottom()))

def free(b, others, margin=0.35, edge=0.9):
    if b[0] < x0 + edge or b[1] < y0 + edge or b[2] > x0 + W - edge or b[3] > y0 + H - edge:
        return False
    return all(b[2] + margin <= o[0] or o[2] + margin <= b[0] or b[3] + margin <= o[1] or o[3] + margin <= b[1] for o in others)

TARGETS = {'X1': (27.5, 67.4), 'X2': (44.5, 67.4), 'SV1': (6.0, 40.5), 'X3': (8.5, 47.0), 'X4': (8.5, 54.0),
           'U405': (64.0, 50.0), 'C408': (60.0, 53.0), 'C409': (68.0, 53.0),
           'J304': (66.0, 9.5), 'C313': (70.2, 6.0), 'L301': (70.2, 13.5), 'R318': (96.0, 2.5), 'R319': (90.0, 2.5),
           'R320': (96.0, 31.0), 'R321': (99.0, 31.0),
           'R423': (30.0, 54.0), 'R424': (33.0, 54.0), 'R425': (50.0, 54.0), 'R426': (53.0, 54.0)}
order = [r for r in TARGETS if r in new]
for ref in order:
    fp = have[ref]
    fp.SetOrientationDegrees(0)
    placed = set(order[:order.index(ref)])
    others = [box(f) for r, f in have.items() if r != ref and not f.IsFlipped() and (r not in new or r in placed)]
    for r, f in have.items():           # parts on the back only block the top side where they have holes through the board
        if f.IsFlipped():
            for pad in f.Pads():
                if pad.GetAttribute() == pcbnew.PAD_ATTRIB_NPTH:
                    q = pad.GetPosition(); rr = tomm(pad.GetDrillSize().x) / 2 + 0.6
                    others.append((tomm(q.x) - rr, tomm(q.y) - rr, tomm(q.x) + rr, tomm(q.y) + rr))
    tx, ty = TARGETS[ref][0] + x0, TARGETS[ref][1] + y0      # targets are relative to the board corner
    fp.SetPosition(pcbnew.VECTOR2I(mm(tx), mm(ty)))
    b0 = box(fp)
    cx, cy = (b0[0] + b0[2]) / 2, (b0[1] + b0[3]) / 2
    fp.Move(pcbnew.VECTOR2I(mm(tx - cx), mm(ty - cy)))          # courtyard centre on the target
    w, h = b0[2] - b0[0], b0[3] - b0[1]
    best = None
    for k in range(0, 4000):                                      # spiral-ish search in 0.5 mm steps
        r = 0.5 * (k ** 0.5) * 2
        a = k * 2.399963
        px, py = tx + r * math.cos(a), ty + r * math.sin(a)
        cand = (px - w / 2, py - h / 2, px + w / 2, py + h / 2)
        if free(cand, others):
            best = (px, py); break
    if best is None:
        print('NO FREE SPOT for', ref); continue
    fp.Move(pcbnew.VECTOR2I(mm(best[0] - tx), mm(best[1] - ty)))
    print(f'placed {ref:5} at ({best[0]:.1f}, {best[1]:.1f}) target ({tx}, {ty})')

# overlap report over the whole top side
tops = [(r, box(f)) for r, f in have.items() if not f.IsFlipped()]
bad = []
for i in range(len(tops)):
    for j in range(i + 1, len(tops)):
        a, b = tops[i][1], tops[j][1]
        if min(a[2], b[2]) - max(a[0], b[0]) > 0.05 and min(a[3], b[3]) - max(a[1], b[1]) > 0.05:
            bad.append((tops[i][0], tops[j][0]))
print('courtyard overlaps:', bad)
board.Save(out)
print('saved', out, '| footprints', len(have))
