"""Loads Freerouting's .ses into the board, adds ground fill on both layers and a board label, saves."""
import sys
import pcbnew
pcb, ses, out = sys.argv[1], sys.argv[2], sys.argv[3]
mm = pcbnew.FromMM
board = pcbnew.LoadBoard(pcb)
print('SES import:', pcbnew.ImportSpecctraSES(board, ses))
bb = board.GetBoardEdgesBoundingBox()
gnd = board.FindNet('GND')
for layer, name in ((pcbnew.F_Cu, 'GND_TOP'), (pcbnew.B_Cu, 'GND_BOTTOM')):
    z = pcbnew.ZONE(board)
    z.SetLayer(layer); z.SetNet(gnd); z.SetZoneName(name)
    z.SetLocalClearance(mm(0.3)); z.SetMinThickness(mm(0.25))
    z.SetThermalReliefGap(mm(0.4)); z.SetThermalReliefSpokeWidth(mm(0.5))
    z.SetPadConnection(pcbnew.ZONE_CONNECTION_THERMAL)
    z.SetIslandRemovalMode(pcbnew.ISLAND_REMOVAL_MODE_ALWAYS)
    ol = z.Outline(); ol.NewOutline()
    for x, y in ((bb.GetLeft(), bb.GetTop()), (bb.GetRight(), bb.GetTop()), (bb.GetRight(), bb.GetBottom()), (bb.GetLeft(), bb.GetBottom())):
        ol.Append(x, y)      # the filler clips it to the rounded outline
    board.Add(z)
pcbnew.ZONE_FILLER(board).Fill(board.Zones())
board.Save(out)
tr = [t for t in board.GetTracks() if t.GetClass() == 'PCB_TRACK']
vias = [t for t in board.GetTracks() if t.GetClass() == 'PCB_VIA']
print('tracks', len(tr), 'vias', len(vias), 'copper length %.0f mm' % sum(pcbnew.ToMM(t.GetLength()) for t in tr))
