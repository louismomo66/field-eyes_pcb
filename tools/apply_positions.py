"""Moves footprints to the centres computed by tools/spread_parts.py."""
import sys, json
import pcbnew
pcb, old_json, new_json, out = sys.argv[1:5]
mm, tomm = pcbnew.FromMM, pcbnew.ToMM
old = json.load(open(old_json))['parts']; new = json.load(open(new_json))
board = pcbnew.LoadBoard(pcb)
moved = 0
for f in board.GetFootprints():
    r = f.GetReference()
    if r in new and not old[r]['back']:
        dx, dy = new[r][0] - old[r]['x'], new[r][1] - old[r]['y']
        if abs(dx) > 1e-6 or abs(dy) > 1e-6:
            f.Move(pcbnew.VECTOR2I(mm(dx), mm(dy))); moved += 1
board.Save(out); print('moved', moved, 'parts')
