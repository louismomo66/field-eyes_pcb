"""Removes a via that sits closer than the hole-to-hole limit to another one (the one without a track on it goes first), then refills the planes."""
import sys, math
import pcbnew
pcb, out = sys.argv[1], sys.argv[2]
board = pcbnew.LoadBoard(pcb)
tomm = pcbnew.ToMM
vias = [t for t in board.GetTracks() if t.GetClass() == 'PCB_VIA']
tr = [t for t in board.GetTracks() if t.GetClass() != 'PCB_VIA']
def has_track(v):
    p = v.GetPosition()
    return any(t.GetNetCode() == v.GetNetCode() and (t.GetStart() == p or t.GetEnd() == p) for t in tr)
gone = []
for i, a in enumerate(vias):
    for b in vias[i + 1:]:
        if a in gone or b in gone: continue
        if math.hypot(tomm(a.GetPosition().x - b.GetPosition().x), tomm(a.GetPosition().y - b.GetPosition().y)) < 0.6:
            gone.append(b if not has_track(b) or has_track(a) else a)
for v in gone: board.Remove(v)
board.Save(out)
pcbnew.ZONE_FILLER(board).Fill(board.Zones())
board.Save(out)
print('vias too close, removed:', len(gone))
