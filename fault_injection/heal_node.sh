#!/bin/bash
# Remove iptables partition rules and restart Qdrant if it was killed.
# Run on the TARGET node.
set -euo pipefail

echo "Flushing iptables rules ..."
sudo iptables -F INPUT
sudo iptables -F OUTPUT

if ! pgrep -x qdrant > /dev/null 2>&1; then
    echo "Qdrant not running, restarting via systemd ..."
    sudo systemctl start qdrant
    sleep 2
    if pgrep -x qdrant > /dev/null 2>&1; then
        echo "Qdrant restarted."
    else
        echo "WARNING: Qdrant failed to restart."
    fi
else
    echo "Qdrant already running."
fi

echo "Heal complete."
