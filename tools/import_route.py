"""Adds the router's tracks and vias (routing/result.txt) to the board, refills the ground planes and reports what was left unrouted."""
import sys, json
import pcbnew
pcb, res, out = sys.argv[1], sys.argv[2], sys.argv[3]
mm = pcbnew.FromMM
meta = json.load(open(res.replace('result.txt', 'board.txt.json')))
board = pcbnew.LoadBoard(pcb)
X0, Y0 = meta['X0'], meta['Y0']
V = lambda x, y: pcbnew.VECTOR2I(mm(X0 + x), mm(Y0 + y))
nets = {}
for code, n in board.GetNetInfo().NetsByNetcode().items():
    nets[str(n.GetNetname()).replace(' ', '_')] = n
ok, fail, nt, nv = [], [], 0, 0
seen = set()   # two ground fan-outs can pick the same via cell: keep one
for line in open(res):
    f = line.split()
    if not f: continue
    if f[0] == 'SEG':
        t = pcbnew.PCB_TRACK(board); t.SetStart(V(float(f[4]), float(f[5]))); t.SetEnd(V(float(f[6]), float(f[7])))
        t.SetWidth(mm(float(f[3]))); t.SetLayer(pcbnew.F_Cu if f[2] == '0' else pcbnew.B_Cu); t.SetNet(nets[f[1]]); board.Add(t); nt += 1
    elif f[0] == 'VIA':
        key = (round(float(f[2]), 2), round(float(f[3]), 2))
        if key in seen: continue
        seen.add(key)
        v = pcbnew.PCB_VIA(board); v.SetPosition(V(float(f[2]), float(f[3]))); v.SetWidth(mm(0.6)); v.SetDrill(mm(0.3))
        v.SetViaType(pcbnew.VIATYPE_THROUGH); v.SetLayerPair(pcbnew.F_Cu, pcbnew.B_Cu); v.SetNet(nets[f[1]]); board.Add(v); nv += 1
    elif f[0] == 'OK': ok.append(f[1] + ('' if float(f[2]) >= 0.25 else ' (0.2 mm)'))
    elif f[0] == 'FAIL': fail.append(f[1])
for fp in board.GetFootprints():          # a header ground pad with only one free side cannot take thermal spokes: connect it solid
    if fp.GetReference() == 'J101':
        for pd in fp.Pads():
            if pd.GetNetname() == 'GND': pd.SetLocalZoneConnection(pcbnew.ZONE_CONNECTION_FULL)
board.Save(out)
pcbnew.ZONE_FILLER(board).Fill(board.Zones())
board.Save(out)
print(f'added {nt} tracks and {nv} vias; routed nets {len(ok)}, unrouted {len(fail)}: {fail}')
