#!/usr/bin/env bash
# Stop all evaporation chamber sensor screens safely (clean version)

set -euo pipefail

# Prevent running from inside a screen session
if [[ -n "${STY-}" ]]; then
  echo "You are currently inside a screen session ($STY)."
  echo "Please detach first (Ctrl+A, D) and run this from a normal shell."
  exit 1
fi

echo "Stopping evaporation chamber sensors..."

stop_one() {
  local name="$1"

  # Check if screen is running
  if ! screen -ls | grep -q "\.${name}"; then
    echo " - ${name}: not running"
    return 0
  fi

  echo " - ${name}: requesting graceful exit..."
  # Try a normal 'exit' command inside the screen
  screen -S "$name" -p 0 -X stuff "exit\n" || true
  sleep 1

  # If still running, force quit
  if screen -ls | grep -q "\.${name}"; then
    echo " - ${name}: force quitting..."
    screen -S "$name" -X quit || true
    sleep 1
  fi

  # Confirm status
  if screen -ls | grep -q "\.${name}"; then
    echo " - ${name}: still running, please check with 'screen -r ${name}'"
  else
    echo " - ${name}: stopped successfully"
  fi
}

stop_one temp
stop_one pressure

echo "All done."

