"""Sets the track-width classes and exports the Specctra DSN that Freerouting reads."""
import sys, json
import pcbnew
pcb, dsn = sys.argv[1], sys.argv[2]
mm = pcbnew.FromMM
CLASSES = {  # name: (track width, clearance, [nets])
    'ModemPower': (0.8, 0.2, ['/MODEM_VBAT']),
    'Power': (0.5, 0.2, ['VSYS', '/SOLAR_RAW', '/SOLAR_P', '/CHG_D', '/CHG_SW', '/CHG_CSP', '/BATN', '/PROT_D',
                         '/SENS_VIN', '/BST_SW', '+12V_SENS', '/VALVE_RES', '/MX_VDD', '/VALVE_A', '/VALVE_B']),
    'Supply': (0.35, 0.2, ['GND', '+3V3', '+3V3_SW', '/VDD_1V8', '/SIM_VDD', '/VALVE_9V']),
    'RF': (0.6, 0.25, ['/RF_ANT', '/ANT_FEED']),
}
board = pcbnew.LoadBoard(pcb)
ns = board.GetDesignSettings().m_NetSettings
names = {str(n.GetNetname()) for n in board.GetNetInfo().NetsByNetcode().values()}
for cname, (w, clr, nets) in CLASSES.items():
    nc = pcbnew.NETCLASS(cname)
    nc.SetTrackWidth(mm(w)); nc.SetClearance(mm(clr)); nc.SetViaDiameter(mm(0.6)); nc.SetViaDrill(mm(0.3))
    ns.SetNetclass(cname, nc)
    for n in nets:
        assert n in names, 'unknown net ' + n
        ns.SetNetclassPatternAssignment(n, cname)
print('DSN export:', pcbnew.ExportSpecctraDSN(board, dsn))
json.dump({k: v for k, v in CLASSES.items()}, open(dsn + '.classes.json', 'w'))
