"""Imports Freerouting's .ses into the board, pours GND on both layers, adds the board label, saves."""
import sys
import pcbnew

src, ses, out, W, H = sys.argv[1], sys.argv[2], sys.argv[3], float(sys.argv[4]), float(sys.argv[5])
mm = pcbnew.FromMM
board = pcbnew.LoadBoard(src)
print('SES import', pcbnew.ImportSpecctraSES(board, ses))

gnd = board.FindNet('GND')
for layer in (pcbnew.F_Cu, pcbnew.B_Cu):
    z = pcbnew.ZONE(board)
    z.SetLayer(layer)
    z.SetNet(gnd)
    z.SetLocalClearance(mm(0.3))
    z.SetMinThickness(mm(0.25))
    z.SetThermalReliefGap(mm(0.4))
    z.SetThermalReliefSpokeWidth(mm(0.5))
    z.SetPadConnection(pcbnew.ZONE_CONNECTION_THERMAL)
    z.SetIslandRemovalMode(pcbnew.ISLAND_REMOVAL_MODE_ALWAYS)
    z.SetZoneName('GND_' + ('TOP' if layer == pcbnew.F_Cu else 'BOTTOM'))
    ol = z.Outline()
    ol.NewOutline()
    for x, y in [(0, 0), (W, 0), (W, H), (0, H)]:   # clipped to the rounded board edge by the filler
        ol.Append(mm(x), mm(y))
    board.Add(z)

# board label on the top silkscreen, in the free space right of the ESP32 support parts
t = pcbnew.PCB_TEXT(board)
t.SetText('FIELD EYES v2  2026-10')
t.SetLayer(pcbnew.F_SilkS)
t.SetTextSize(pcbnew.VECTOR2I(mm(1.2), mm(1.2)))
t.SetTextThickness(mm(0.18))
t.SetPosition(pcbnew.VECTOR2I(mm(float(sys.argv[6]) if len(sys.argv) > 6 else 48), mm(float(sys.argv[7]) if len(sys.argv) > 7 else H - 1.6)))
board.Add(t)

filler = pcbnew.ZONE_FILLER(board)
filler.Fill(board.Zones())
board.Save(out)

tracks = [t for t in board.GetTracks() if t.GetClass() == 'PCB_TRACK']
vias = [t for t in board.GetTracks() if t.GetClass() == 'PCB_VIA']
print('tracks', len(tracks), 'vias', len(vias), 'length %.0f mm' % sum(pcbnew.ToMM(t.GetLength()) for t in tracks))
