"""After routing, the signal tracks cut both ground planes into pieces. This joins every piece to the plane on the other layer with
the fewest vias: a via goes only where both planes have copper all around it (so it is clear of every other net), and only if it
connects two pieces that are not yet joined. Dangling vias from the grid stitching are removed first."""
import sys, math, itertools
import pcbnew
pcb, out = sys.argv[1], sys.argv[2]
mm, tomm = pcbnew.FromMM, pcbnew.ToMM
board = pcbnew.LoadBoard(pcb)
bb = board.GetBoardEdgesBoundingBox()
X0, Y0 = tomm(bb.GetLeft()) + 0.05, tomm(bb.GetTop()) + 0.05
W, H = tomm(bb.GetWidth()) - 0.1, tomm(bb.GetHeight()) - 0.1
V = lambda x, y: pcbnew.VECTOR2I(mm(X0 + x), mm(Y0 + y))
gnd = board.FindNet('GND')
zones = {z.GetLayer(): z for z in board.Zones() if not z.GetIsRuleArea() and z.GetNetname() == 'GND'}
fills = {ly: z.GetFilledPolysList(ly) for ly, z in zones.items()}
boxes = {}
for ly, fp in fills.items():
    boxes[ly] = []
    for o in range(fp.OutlineCount()):
        c = fp.COutline(o); xs = [c.CPoint(i).x for i in range(c.PointCount())]; ys = [c.CPoint(i).y for i in range(c.PointCount())]
        boxes[ly].append((min(xs), min(ys), max(xs), max(ys)))
def frag(ly, p):
    fp = fills[ly]
    for o, (x0, y0, x1, y1) in enumerate(boxes[ly]):
        if x0 <= p.x <= x1 and y0 <= p.y <= y1 and fp.Contains(p, o): return o
    return None
RING = [(0.34 * math.cos(a * math.pi / 4), 0.34 * math.sin(a * math.pi / 4)) for a in range(8)]
def solid(ly, x, y):
    f = frag(ly, V(x, y))
    if f is None: return None
    for dx, dy in RING:
        if frag(ly, V(x + dx, y + dy)) != f: return None
    return f
F, B = pcbnew.F_Cu, pcbnew.B_Cu
parent = {}
def find(a):
    parent.setdefault(a, a)
    while parent[a] != a:
        parent[a] = parent[parent[a]]; a = parent[a]
    return a
def union(a, b):
    a, b = find(a), find(b)
    if a != b: parent[a] = b; return True
    return False
# existing joins: vias and through-hole ground pads
vias = [t for t in board.GetTracks() if t.GetClass() == 'PCB_VIA' and t.GetNetname() == 'GND']
gx = []
dead = []
for v in vias:
    p = v.GetPosition(); a, b = frag(F, p), frag(B, p)
    gx.append((tomm(p.x) - X0, tomm(p.y) - Y0))
    if (a is None or b is None) and not any(t.GetClass() != 'PCB_VIA' and t.GetNetname() == 'GND' and (t.GetStart() == p or t.GetEnd() == p) for t in board.GetTracks()): dead.append(v)
    elif a is None or b is None: pass
    else: union((F, a), (B, b))
for f in board.GetFootprints():
    for pd in f.Pads():
        if pd.GetNetname() != 'GND': continue
        p = pd.GetPosition(); a, b = frag(F, p), frag(B, p)
        gx.append((tomm(p.x) - X0, tomm(p.y) - Y0))
        if pd.IsOnLayer(F) and pd.IsOnLayer(B) and a is not None and b is not None: union((F, a), (B, b))
for ly in (F, B):
    for o in range(len(boxes[ly])): find((ly, o))
print('pieces: top', len(boxes[F]), 'bottom', len(boxes[B]), '| dangling vias to remove:', len(dead))
for v in dead: board.Remove(v)
added = 0
for ix in range(int(W / 0.8)):
    for iy in range(int(H / 0.8)):
        x, y = 0.4 + ix * 0.8, 0.4 + iy * 0.8
        a = solid(F, x, y)
        if a is None: continue
        b = solid(B, x, y)
        if b is None: continue
        if find((F, a)) == find((B, b)): continue
        if any(math.hypot(x - qx, y - qy) < 1.0 for qx, qy in gx): continue
        v = pcbnew.PCB_VIA(board); v.SetPosition(V(x, y)); v.SetWidth(mm(0.6)); v.SetDrill(mm(0.3))
        v.SetViaType(pcbnew.VIATYPE_THROUGH); v.SetLayerPair(F, B); v.SetNet(gnd); board.Add(v)
        gx.append((x, y)); union((F, a), (B, b)); added += 1
roots = {}
for k in list(parent): roots.setdefault(find(k), []).append(k)
print('vias added:', added, '| groups left:', len(roots), sorted(len(v) for v in roots.values())[-5:])
board.Save(out)
pcbnew.ZONE_FILLER(board).Fill(board.Zones())
board.Save(out)
