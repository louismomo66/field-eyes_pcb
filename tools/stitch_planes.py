"""Ties the two ground planes together with vias on a grid wherever there is free copper (so that no ground fragment is left floating)."""
import sys, math
import pcbnew
pcb, out = sys.argv[1], sys.argv[2]
step = float(sys.argv[3]) if len(sys.argv) > 3 else 3.0
mm, tomm = pcbnew.FromMM, pcbnew.ToMM
board = pcbnew.LoadBoard(pcb)
bb = board.GetBoardEdgesBoundingBox()
X0, Y0 = tomm(bb.GetLeft()) + 0.05, tomm(bb.GetTop()) + 0.05
W, H = tomm(bb.GetWidth()) - 0.1, tomm(bb.GetHeight()) - 0.1
ESP_KO = (30.2, 0.0, 78.2, 9.4)
gnd = board.FindNet('GND')
V = lambda x, y: pcbnew.VECTOR2I(mm(X0 + x), mm(Y0 + y))
fps = list(board.GetFootprints())
tracks = list(board.GetTracks())
def free(x, y):
    p = V(x, y)
    if ESP_KO[0] <= x <= ESP_KO[2] and ESP_KO[1] <= y <= ESP_KO[3]: return False
    for f in fps:
        if f.GetReference() == 'J302':
            bx = f.GetBoundingBox(False); m = mm(0.8)
            if bx.GetLeft() - m <= p.x <= bx.GetRight() + m and bx.GetTop() - m <= p.y <= bx.GetBottom() + m: return False
        for pd in f.Pads():
            if pd.HitTest(p, mm(0.65)): return False
    for t in tracks:
        if t.HitTest(p, mm(0.6)): return False
    for z in board.Zones():
        if z.GetIsRuleArea() and z.Outline().Contains(p): return False
    return True
def inside(x, y, rad=4.0, m=1.0):
    cx = min(max(x, rad), W - rad); cy = min(max(y, rad), H - rad)
    return math.hypot(x - cx, y - cy) <= rad - m
n = 0
y = 2.0
while y < H - 1.5:
    x = 2.0 + (step / 2 if int(y / step) % 2 else 0)
    while x < W - 1.5:
        if inside(x, y) and free(x, y):
            v = pcbnew.PCB_VIA(board); v.SetPosition(V(x, y)); v.SetWidth(mm(0.6)); v.SetDrill(mm(0.3))
            v.SetViaType(pcbnew.VIATYPE_THROUGH); v.SetLayerPair(pcbnew.F_Cu, pcbnew.B_Cu); v.SetNet(gnd); board.Add(v)
            tracks.append(v); n += 1
        x += step
    y += step
board.Save(out)
pcbnew.ZONE_FILLER(board).Fill(board.Zones())
board.Save(out)
print('stitching vias added:', n)
