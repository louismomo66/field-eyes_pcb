"""Writes the board geometry for tools/router.cpp: outline, pads (copper outlines per layer), holes, keep-outs, existing tracks and vias,
and the connections still to be made (every net except GND, which the two ground planes take care of, and the antenna lines that are already routed)."""
import sys, json
import pcbnew
pcb, out = sys.argv[1], sys.argv[2]
tomm = pcbnew.ToMM
board = pcbnew.LoadBoard(pcb)
bb = board.GetBoardEdgesBoundingBox()
X0, Y0 = tomm(bb.GetLeft()) + 0.05, tomm(bb.GetTop()) + 0.05
W, H = tomm(bb.GetWidth()) - 0.1, tomm(bb.GetHeight()) - 0.1
P = lambda v: (tomm(v.x) - X0, tomm(v.y) - Y0)
CLASSES = json.load(open(__file__.replace('export_route.py', '../routing/field_eyes_v2.dsn.classes.json')))
width_of = {}
for name, (w, clr, nets) in CLASSES.items():
    for n in nets: width_of[n] = w
RF_NETS = ('/GPS_ANT', '/GPS_SIG', '/GPS_BIAS', '/RF_ANT', '/ANT_FEED')
SKIP = ('GND',) + RF_NETS

nets = {}
for code, n in board.GetNetInfo().NetsByNetcode().items():
    if str(n.GetNetname()): nets[str(n.GetNetname())] = len(nets) + 1
L = []
L.append(f'GRID {W:.3f} {H:.3f}')
outs = pcbnew.SHAPE_POLY_SET(); board.GetBoardPolygonOutlines(outs); ol = outs.COutline(0)
L.append('OUTLINE ' + str(ol.PointCount()) + ' ' + ' '.join('%.3f %.3f' % P(ol.CPoint(i)) for i in range(ol.PointCount())))
for name, i in nets.items():
    L.append(f'NET {i} {width_of.get(name, 0.25)} {name.replace(" ", "_")}')

def poly(layer, netid, shp):
    for o in range(shp.OutlineCount()):
        c = shp.COutline(o)
        L.append(f'POLY {layer} {netid} {c.PointCount()} ' + ' '.join('%.3f %.3f' % P(c.CPoint(i)) for i in range(c.PointCount())))

terms = {}
for f in board.GetFootprints():
    for g in f.GraphicalItems():                      # copper drawn in the footprint (the SIM tray's shield tabs) is an obstacle too
        for li, ly in enumerate((pcbnew.F_Cu, pcbnew.B_Cu)):
            if g.GetLayer() == ly and g.GetClass() == 'PCB_SHAPE':
                shp = pcbnew.SHAPE_POLY_SET()
                g.TransformShapeToPolygon(shp, ly, 0, pcbnew.FromMM(0.01), pcbnew.ERROR_INSIDE)
                poly(li, 0, shp)
    for p in f.Pads():
        net = str(p.GetNetname()); nid = nets.get(net, 0)
        mask = 0
        for li, ly in enumerate((pcbnew.F_Cu, pcbnew.B_Cu)):
            if p.IsOnLayer(ly):
                poly(li, nid, p.GetEffectivePolygon(ly)); mask |= 1 << li
        d = p.GetDrillSize()
        if tomm(d.x) > 0 and not p.HasHole() is False and p.GetAttribute() == pcbnew.PAD_ATTRIB_NPTH:
            x, y = P(p.GetPosition()); L.append(f'HOLE {x:.3f} {y:.3f} {tomm(d.x) / 2:.3f}')
        if mask and nid and net not in SKIP:
            x, y = P(p.GetPosition()); terms.setdefault(net, []).append((mask, x, y, f.GetReference() + '.' + str(p.GetNumber())))
for t in board.GetTracks():
    nid = nets.get(str(t.GetNetname()), 0)
    if t.GetClass() == 'PCB_VIA':
        x, y = P(t.GetPosition()); L.append(f'VIA {nid} {x:.3f} {y:.3f} {tomm(t.GetWidth()):.3f}')
    else:
        a, b = P(t.GetStart()), P(t.GetEnd())
        L.append(f'SEG {0 if t.GetLayer() == pcbnew.F_Cu else 1} {nid} {tomm(t.GetWidth()):.3f} {a[0]:.3f} {a[1]:.3f} {b[0]:.3f} {b[1]:.3f}')
zs = list(board.Zones()) + [z for f in board.GetFootprints() for z in f.Zones()]
for z in zs:
    if z.GetIsRuleArea() and z.GetDoNotAllowTracks():
        for ly in z.GetLayerSet().Seq():
            if ly in (pcbnew.F_Cu, pcbnew.B_Cu):
                c = z.Outline().COutline(0)
                L.append(f'KEEP {0 if ly == pcbnew.F_Cu else 1} {c.PointCount()} ' + ' '.join('%.3f %.3f' % P(c.CPoint(i)) for i in range(c.PointCount())))
n_conn = 0
for net, ts in terms.items():
    if len(ts) < 2: continue
    L.append(f'ROUTE {nets[net]} {len(ts)} ' + ' '.join(f'{m} {x:.3f} {y:.3f}' for m, x, y, _ in ts))
    n_conn += len(ts) - 1
open(out, 'w').write('\n'.join(L) + '\n')
json.dump({'X0': X0, 'Y0': Y0, 'nets': nets, 'terms': {k: [t[3] for t in v] for k, v in terms.items()}}, open(out + '.json', 'w'))
print('nets to route:', len([1 for v in terms.values() if len(v) > 1]), '| connections:', n_conn)
