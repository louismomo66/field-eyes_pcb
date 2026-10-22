"""Finds the ground pads that the signal tracks have cut off from both ground planes and writes one 'route to the nearest ground via'
connection for each (appended to the router's input file) so that the router draws a short ground track for them."""
import sys, math, json
import pcbnew
pcb, board_txt = sys.argv[1], sys.argv[2]
src = open(__file__.replace('gnd_links.py', 'stitch_fragments.py')).read().split("print('pieces:")[0]
src = src.replace("pcb, out = sys.argv[1], sys.argv[2]", "")
exec(src)
vias = [t for t in board.GetTracks() if t.GetClass() == 'PCB_VIA' and t.GetNetname() == 'GND']
for v in vias:
    p = v.GetPosition(); a, b = frag(F, p), frag(B, p)
    if a is not None and b is not None: union((F, a), (B, b))
for f in board.GetFootprints():
    for pd in f.Pads():
        if pd.GetNetname() != 'GND': continue
        p = pd.GetPosition(); a, b = frag(F, p), frag(B, p)
        if pd.IsOnLayer(F) and pd.IsOnLayer(B) and a is not None and b is not None: union((F, a), (B, b))
for ly in (F, B):
    for o in range(len(boxes[ly])): find((ly, o))
roots = {}
for k in list(parent): roots.setdefault(find(k), []).append(k)
mainset = set(max(roots.values(), key=len))
# main-group vias are the targets
targets = []
for v in vias:
    p = v.GetPosition(); a, b = frag(F, p), frag(B, p)
    if a is not None and (F, a) in mainset: targets.append((tomm(p.x) - X0, tomm(p.y) - Y0))
meta = json.load(open(board_txt + '.json')); gid = meta['nets']['GND']
lines = []; fans = []
for f in board.GetFootprints():
    for pd in f.Pads():
        if pd.GetNetname() != 'GND': continue
        p = pd.GetPosition(); inmain = False; mask = 0
        for li, ly in enumerate((F, B)):
            if pd.IsOnLayer(ly):
                mask |= 1 << li
                fr = frag(ly, p)
                if fr is not None and (ly, fr) in mainset: inmain = True
        if inmain or not mask: continue
        x, y = tomm(p.x) - X0, tomm(p.y) - Y0
        near = sorted(targets, key=lambda t: math.hypot(t[0] - x, t[1] - y))[:8]
        fans.append(f'{mask} {x:.3f} {y:.3f}')
        lines.append(f'ROUTEANY {gid} {1 + len(near)} {mask} {x:.3f} {y:.3f} ' + ' '.join(f'3 {tx:.3f} {ty:.3f}' for tx, ty in near))
open(board_txt.replace('.txt', '_fan.txt'), 'w').write('\n'.join(fans) + '\n')
open(board_txt, 'a').write('\n'.join(lines) + '\n')
print('ground pads to link:', len(lines))
