#!/bin/bash
# Bootstrap a 3-node Qdrant cluster from node0.
# Prerequisites:
#   - Qdrant running on all 3 nodes (single-node mode or cluster mode)
#   - config/nodes.yaml has correct IPs
# Run from node0: bash setup/configure_cluster.sh
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_DIR"

NODES_CONFIG="${REPO_DIR}/config/nodes.yaml"

# Parse node IPs from YAML (simple grep, no yaml parser needed)
NODE0_HOST=$(grep -A5 'id: 0' "$NODES_CONFIG" | grep 'host:' | head -1 | awk '{print $2}')
NODE1_HOST=$(grep -A5 'id: 1' "$NODES_CONFIG" | grep 'host:' | head -1 | awk '{print $2}')
NODE2_HOST=$(grep -A5 'id: 2' "$NODES_CONFIG" | grep 'host:' | head -1 | awk '{print $2}')
P2P_PORT=6335

echo "==> Nodes: ${NODE0_HOST}, ${NODE1_HOST}, ${NODE2_HOST}"

if [[ "$NODE1_HOST" == "NODE1_IP" || "$NODE2_HOST" == "NODE2_IP" ]]; then
    echo "ERROR: Fill in NODE1_IP and NODE2_IP in config/nodes.yaml first."
    exit 1
fi

echo "==> Adding node1 (${NODE1_HOST}) to cluster ..."
curl -sf -X POST "http://${NODE0_HOST}:6333/cluster/peer" \
    -H 'Content-Type: application/json' \
    -d "{\"uri\": \"http://${NODE1_HOST}:${P2P_PORT}\"}"

echo ""
echo "==> Adding node2 (${NODE2_HOST}) to cluster ..."
curl -sf -X POST "http://${NODE0_HOST}:6333/cluster/peer" \
    -H 'Content-Type: application/json' \
    -d "{\"uri\": \"http://${NODE2_HOST}:${P2P_PORT}\"}"

echo ""
echo "==> Waiting for all peers to become Active ..."
for i in $(seq 1 30); do
    STATUS=$(curl -sf "http://${NODE0_HOST}:6333/cluster" 2>/dev/null || echo "{}")
    ACTIVE=$(echo "$STATUS" | python3 -c "
import sys, json
d = json.load(sys.stdin)
peers = d.get('result', {}).get('peers', {})
active = sum(1 for p in peers.values() if p.get('state') == 'Active')
total = len(peers)
print(f'{active}/{total}')
" 2>/dev/null || echo "0/0")
    echo "  Active peers: ${ACTIVE}"
    if [[ "$ACTIVE" == "3/3" ]]; then
        echo "==> Cluster ready!"
        break
    fi
    sleep 2
done

echo ""
curl -s "http://${NODE0_HOST}:6333/cluster" | python3 -m json.tool
