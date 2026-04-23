#!/bin/bash
# Kill the Qdrant process with SIGKILL. Run on the target node.
set -euo pipefail

# Stop via systemd so the unit is marked inactive and won't auto-restart.
# This simulates a hard crash for the experiment's fault window.
if systemctl is-active --quiet qdrant; then
    sudo systemctl stop qdrant
    echo "Qdrant stopped (SIGKILL via systemd)."
else
    echo "Qdrant is not running."
fi
