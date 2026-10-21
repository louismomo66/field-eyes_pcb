"""Dumps part boxes, nets and obstacles of the board to JSON (for tools/spread_parts.py)."""
import sys, json, os
import pcbnew
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import netlist
pcb, net_path, out = sys.argv[1], sys.argv[2], sys.argv[3]
tomm = pcbnew.ToMM
board = pcbnew.LoadBoard(pcb)
bb = board.GetBoardEdgesBoundingBox()
X0, Y0 = tomm(bb.GetLeft()) + 0.05, tomm(bb.GetTop()) + 0.05
W, H = tomm(bb.GetWidth()) - 0.1, tomm(bb.GetHeight()) - 0.1
comps, nets = netlist.load(net_path)
parts = {}
for f in board.GetFootprints():
    r = f.GetReference()
    cy = f.GetCourtyard(pcbnew.B_CrtYd if f.IsFlipped() else pcbnew.F_CrtYd)
    b = cy.BBox() if cy.OutlineCount() else f.GetBoundingBox(False, False)
    x0, y0, x1, y1 = (tomm(b.GetLeft()) - X0, tomm(b.GetTop()) - Y0, tomm(b.GetRight()) - X0, tomm(b.GetBottom()) - Y0)
    p = f.GetPosition()
    d = dict(ref=r, x=(x0 + x1) / 2, y=(y0 + y1) / 2, w=x1 - x0, h=y1 - y0, back=f.IsFlipped(),
             ox=tomm(p.x) - X0, oy=tomm(p.y) - Y0, rot=f.GetOrientationDegrees())
    if r == 'U301':      # imported modem footprint: use its 24 x 24 body
        d.update(x=d['ox'], y=d['oy'], w=25.2, h=25.2)
    if r == 'U201':      # module body plus the antenna end, which must stay free of parts
        d.update(x=d['ox'], y=(0 + d['oy'] + 10.0) / 2, w=18.8, h=d['oy'] + 10.0)
    parts[r] = d
pegs = []
for pad in [p for f in board.GetFootprints() if f.GetReference() == 'BT101' for p in f.Pads()]:
    if pad.GetAttribute() == pcbnew.PAD_ATTRIB_NPTH:
        q = pad.GetPosition(); r = tomm(pad.GetDrillSize().x) / 2 + 0.7
        pegs.append([tomm(q.x) - X0 - r, tomm(q.y) - Y0 - r, tomm(q.x) - X0 + r, tomm(q.y) - Y0 + r])
m = [pd for f in board.GetFootprints() if f.GetReference() == 'U301' for pd in f.Pads() if pd.GetNumber() == 'P$90'][0].GetPosition()
gx, gy = tomm(m.x) - X0, tomm(m.y) - Y0
pegs.append([gx - 9.7, 8.6, gx + 3.2, gy + 3.0])                    # GPS antenna corridor: only the GPS parts may sit here
u = parts['U201']
pegs.append([u['ox'] - 24.0, 0.0, u['ox'] + 24.0, u['oy'] - 9.0])      # antenna keep-out of the ESP32 module: no parts, no copper
json.dump(dict(W=W, H=H, parts=parts, nets={n: sorted({r for r, _ in nodes}) for n, nodes in nets.items()}, pegs=pegs), open(out, 'w'))
print('exported', len(parts), 'parts', len(nets), 'nets; board', round(W, 1), 'x', round(H, 1))
