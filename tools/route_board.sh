#!/bin/zsh
# Routes the whole board from the placed, antenna-routed board (backups/before_full_routing.kicad_pcb) into field_eyes_v2.kicad_pcb.
#   1. SV1 moves out of the ESP32 antenna keep-out   2. export   3. fan-out lines for the ground pads that need their own via
#   3b. links from ground pieces that the previous run left cut off (routing/gnd_any.txt, written by tools/gnd_groups.py)
#   4. route (tools/router.cpp, build with clang++ -O2 -std=c++17)   5. import + refill planes   6. join the ground pieces with vias
cd "$(dirname "$0")/.."
PY=/Applications/KiCad/KiCad.app/Contents/Frameworks/Python.framework/Versions/Current/bin/python3
SRC=backups/before_full_routing.kicad_pcb
$PY tools/move_sv1.py $SRC field_eyes_v2.kicad_pcb 2>&1 | grep -e Error -e Trace
$PY tools/export_route.py field_eyes_v2.kicad_pcb routing/board.txt 2>&1 | grep -e nets -e Error
GNDID=$(python3 -c "import json;print(json.load(open('routing/board.txt.json'))['nets']['GND'])")
awk -v g=$GNDID '{print "ROUTEFAN " g " 1 " $1 " " $2 " " $3}' routing/gnd_fan.txt >> routing/board.txt
[ -s routing/gnd_any.txt ] && awk -v g=$GNDID '{n=1+(NF-3)/3; printf "ROUTEANY %s %d", g, n; for(i=1;i<=NF;i++) printf " %s", $i; printf "\n"}' routing/gnd_any.txt >> routing/board.txt
./tools/router routing/board.txt routing/result.txt ${1:-120} 2>&1 | grep -v "^iteration"
$PY tools/import_route.py field_eyes_v2.kicad_pcb routing/result.txt field_eyes_v2.kicad_pcb 2>&1 | grep -e added -e Error -e Trace
$PY tools/stitch_fragments.py field_eyes_v2.kicad_pcb field_eyes_v2.kicad_pcb 2>&1 | grep -e pieces -e vias -e Error -e Trace
$PY tools/gnd_groups.py field_eyes_v2.kicad_pcb field_eyes_v2.kicad_pcb routing/gnd_any.txt 2>&1 | grep -e removed -e Error -e Trace
$PY tools/dedupe_vias.py field_eyes_v2.kicad_pcb field_eyes_v2.kicad_pcb 2>&1 | grep -e removed -e Error -e Trace
