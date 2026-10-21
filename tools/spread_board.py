"""Opens routing channels: inserts empty strips across the board at chosen lines (parts to the right of / below a line move
rigidly), then redraws the rounded outline. Parts keep their relative positions inside each block."""
import sys, math
import pcbnew
pcb, out = sys.argv[1], sys.argv[2]
GAP = float(sys.argv[3]) if len(sys.argv) > 3 else 4.0
VCUTS = [20, 40, 60, 80]      # vertical lines (mm from the left edge)
HCUTS = [24, 36, 50]          # horizontal lines (mm from the top edge)
RAD = 4.0
mm, tomm = pcbnew.FromMM, pcbnew.ToMM
board = pcbnew.LoadBoard(pcb)
bb = board.GetBoardEdgesBoundingBox()
x0, y0 = tomm(bb.GetLeft()) + 0.05, tomm(bb.GetTop()) + 0.05
W, H = tomm(bb.GetWidth()) - 0.1, tomm(bb.GetHeight()) - 0.1
print(f'board {W:.1f} x {H:.1f} mm at ({x0:.1f}, {y0:.1f})')
for fp in board.GetFootprints():
    p = fp.GetPosition()
    lx, ly = tomm(p.x) - x0, tomm(p.y) - y0
    dx = GAP * sum(1 for c in VCUTS if lx > c)
    dy = GAP * sum(1 for c in HCUTS if ly > c)
    fp.Move(pcbnew.VECTOR2I(mm(dx), mm(dy)))
W2, H2 = W + GAP * len(VCUTS), H + GAP * len(HCUTS)
for d in list(board.GetDrawings()):
    if d.GetLayer() == pcbnew.Edge_Cuts:
        board.Remove(d)
def line(a, b):
    s = pcbnew.PCB_SHAPE(board, pcbnew.SHAPE_T_SEGMENT)
    s.SetStart(pcbnew.VECTOR2I(mm(x0 + a[0]), mm(y0 + a[1]))); s.SetEnd(pcbnew.VECTOR2I(mm(x0 + b[0]), mm(y0 + b[1])))
    s.SetLayer(pcbnew.Edge_Cuts); s.SetWidth(mm(0.1)); board.Add(s)
def arc(c, start):
    s = pcbnew.PCB_SHAPE(board, pcbnew.SHAPE_T_ARC)
    pt = lambda a: pcbnew.VECTOR2I(mm(x0 + c[0] + RAD * math.cos(math.radians(a))), mm(y0 + c[1] + RAD * math.sin(math.radians(a))))
    s.SetArcGeometry(pt(start), pt(start + 45), pt(start + 90))
    s.SetLayer(pcbnew.Edge_Cuts); s.SetWidth(mm(0.1)); board.Add(s)
line((RAD, 0), (W2 - RAD, 0)); line((W2, RAD), (W2, H2 - RAD)); line((W2 - RAD, H2), (RAD, H2)); line((0, H2 - RAD), (0, RAD))
arc((W2 - RAD, RAD), 270); arc((W2 - RAD, H2 - RAD), 0); arc((RAD, H2 - RAD), 90); arc((RAD, RAD), 180)
board.Save(out)
print(f'new board {W2:.1f} x {H2:.1f} mm, rounded corners {RAD} mm')
