"""Moves the programming header SV1 out of the ESP32 antenna keep-out (its pads could not be routed there); R205-R207 make room by moving down."""
import sys, pcbnew
pcb, out = sys.argv[1], sys.argv[2]
mm = pcbnew.FromMM
board = pcbnew.LoadBoard(pcb)
for f in board.GetFootprints():
    if f.GetReference() == 'SV1': f.SetPosition(pcbnew.VECTOR2I(f.GetPosition().x, f.GetPosition().y + mm(6.4)))
    if f.GetReference() in ('R205', 'R206', 'R207'): f.SetPosition(pcbnew.VECTOR2I(f.GetPosition().x, f.GetPosition().y + mm(2.0)))
board.Save(out)
