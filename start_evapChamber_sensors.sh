# Old scrip start

#!/bin/bash
#python /home/pi/evaporation_chamber/Temp_sensors/evap_chamber_temp_sensors_x2.py &> /dev/null &
#python /home/pi/Pressure_TPG362/pressure_TPG362.py &> /dev/null &

#!/usr/bin/env bash
# Launch temp & pressure sensors without logs

set -euo pipefail

DIR="$HOME/evapchamber_sensors"

# Sanity checks
command -v screen >/dev/null 2>&1 || { echo "ERROR: 'screen' not found."; exit 1; }
[[ -d "$DIR" ]] || { echo "ERROR: Directory '$DIR' not found."; exit 1; }

# Kill old sessions if still running
screen -S temp -X quit 2>/dev/null || true
screen -S pressure -X quit 2>/dev/null || true

# Start both scripts in background screens
screen -dmS temp bash -lc "cd '$DIR'; source ~/.bashrc; python temp_sensors_start.py"
screen -dmS pressure bash -lc "cd '$DIR'; source ~/.bashrc; python pressure_sensors_start.py"

echo "✅ Started sensors:"
echo "  - screen -r temp"
echo "  - screen -r pressure"
echo
echo "To stop them:"
echo "  screen -S temp -X quit"
echo "  screen -S pressure -X quit"

