"""Ground bookkeeping after a routing run. Pieces of the two ground planes that are not joined to the main ground are of two kinds:
  - pieces with no ground pad (only a stitching via keeps them alive): the vias are removed, the pieces then disappear;
  - pieces that hold ground pads (the signal tracks cut them off): one 'reach any ground pad of the main ground' connection each is written
    to the file given, and route_board.sh adds those to the next routing run so the router makes room for them among the signals.
usage: gnd_groups.py in.kicad_pcb out.kicad_pcb links.txt"""
import sys, math
import pcbnew
pcb, out, linkfile = sys.argv[1], sys.argv[2], sys.argv[3]
src = open(__file__.replace('gnd_groups.py', 'stitch_fragments.py')).read().split("print('pieces:")[0]
exec(src.replace("pcb, out = sys.argv[1], sys.argv[2]", ""))
gvias = [t for t in board.GetTracks() if t.GetClass() == 'PCB_VIA' and t.GetNetname() == 'GND']
for v in gvias:
    p = v.GetPosition(); a, b = frag(F, p), frag(B, p)
    if a is not None and b is not None: union((F, a), (B, b))
PT = lambda q: ('pt', int(q.x) // 1000, int(q.y) // 1000)
for v in gvias:
    q = v.GetPosition(); union(PT(q), PT(q))
    for ly in (F, B):
        fr = frag(ly, q)
        if fr is not None: union(PT(q), (ly, fr))
gtracks = [t for t in board.GetTracks() if t.GetClass() != 'PCB_VIA' and t.GetNetname() == 'GND']
for t in gtracks:
    a, b = t.GetStart(), t.GetEnd(); union(PT(a), PT(b))
    ly = t.GetLayer()
    for q in (a, b):
        fr = frag(ly, q)
        if fr is not None: union(PT(q), (ly, fr))
tends = [(t.GetStart(), t.GetLayer()) for t in gtracks] + [(t.GetEnd(), t.GetLayer()) for t in gtracks]
padinfo = []
for f in board.GetFootprints():
    for pd in f.Pads():
        if pd.GetNetname() != 'GND': continue
        p = pd.GetPosition(); mask = 0; nodes = set()
        both = pd.IsOnLayer(F) and pd.IsOnLayer(B)
        r = max(tomm(pd.GetSize().x), tomm(pd.GetSize().y)) / 2 + (0.6 if both else 0.0)
        pts = [p] if not both else [pcbnew.VECTOR2I(p.x + int(mm(r) * math.cos(k * math.pi / 6)), p.y + int(mm(r) * math.sin(k * math.pi / 6))) for k in range(12)]
        for li, ly in enumerate((F, B)):
            if pd.IsOnLayer(ly):
                mask |= 1 << li
                for q in pts:
                    fr = frag(ly, q)
                    if fr is not None: nodes.add((ly, fr))
        nodes = list(nodes)
        for n in nodes[1:]: union(nodes[0], n)
        padkey = ('pad', f.GetReference() + '.' + str(pd.GetNumber()))
        union(padkey, padkey)
        for n in nodes: union(padkey, n)
        for q, ly in tends:
            if pd.IsOnLayer(ly) and pd.HitTest(q, 0): union(padkey, PT(q))
        nodes = [padkey]
        padinfo.append((f.GetReference() + '.' + str(pd.GetNumber()), mask, tomm(p.x) - X0, tomm(p.y) - Y0, nodes))
for ly in (F, B):
    for o in range(len(boxes[ly])): find((ly, o))
comps = {}
for nm, mask, x, y, nodes in padinfo:
    comps.setdefault(find(nodes[0]), []).append((nm, mask, x, y))
main = max(comps.values(), key=len)
mainroot = find(next(nodes[0] for nm, m, x, y, nodes in padinfo if (nm, m, x, y) == main[0]))
dead = []
for v in gvias:
    p = v.GetPosition(); a = frag(F, p)
    if a is not None and find((F, a)) != mainroot and find((F, a)) not in comps: dead.append(v)
for v in dead: board.Remove(v)
lines = []
for key, pads in comps.items():
    if pads is main: continue
    best = None
    for nm, mask, x, y in pads:
        d = min(math.hypot(x - mx, y - my) for _, _, mx, my in main)
        if best is None or d < best[0]: best = (d, nm, mask, x, y)
    _, nm, mask, x, y = best
    near = sorted(main, key=lambda m: math.hypot(x - m[2], y - m[3]))[:12]
    lines.append(f'{mask} {x:.3f} {y:.3f} ' + ' '.join(f'{m[1]} {m[2]:.3f} {m[3]:.3f}' for m in near))
    print('ground pads cut off from the main ground:', [p[0] for p in pads][:6], '| link from', nm)
import os        # cumulative: a link asked for in an earlier run stays, so the runs converge instead of swapping which pieces are cut off
old = open(linkfile).read().splitlines() if os.path.exists(linkfile) else []
allk = {' '.join(l.split()[1:3]): l for l in old}
for l in lines: allk[' '.join(l.split()[1:3])] = l
open(linkfile, 'w').write('\n'.join(allk.values()) + '\n')
print('dead stitching vias removed:', len(dead), '| groups to link:', len(lines), '| main ground pads:', len(main))
board.Save(out)
pcbnew.ZONE_FILLER(board).Fill(board.Zones())
board.Save(out)
