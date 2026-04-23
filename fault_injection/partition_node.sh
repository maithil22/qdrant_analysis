#!/bin/bash
# Drop all Qdrant inter-node traffic using iptables.
# Usage: partition_node.sh <peer_ip1> [<peer_ip2> ...]
# Run on the TARGET node (the one to isolate).
set -euo pipefail

if [ $# -eq 0 ]; then
    echo "Usage: $0 <peer_ip1> [<peer_ip2> ...]"
    exit 1
fi

QDRANT_PORTS=(6333 6334 6335)

for PEER_IP in "$@"; do
    for PORT in "${QDRANT_PORTS[@]}"; do
        sudo iptables -A INPUT  -s "$PEER_IP" -p tcp --dport "$PORT" -j DROP
        sudo iptables -A OUTPUT -d "$PEER_IP" -p tcp --dport "$PORT" -j DROP
    done
    echo "Partitioned peer ${PEER_IP} (ports ${QDRANT_PORTS[*]})"
done

echo "iptables INPUT rules:"
sudo iptables -L INPUT -n --line-numbers | grep DROP
