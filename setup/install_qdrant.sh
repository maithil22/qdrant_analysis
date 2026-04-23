#!/bin/bash
# Install Qdrant binary and configure systemd service.
# Usage: NODE_ID=0 bash setup/install_qdrant.sh
#   NODE_ID=0 uses config/qdrant/node0.yaml (cluster mode)
#   Omit NODE_ID (or set to "single") to use single_node.yaml
set -euo pipefail

QDRANT_VERSION="v1.13.6"
INSTALL_DIR="/usr/local/bin"
NODE_ID="${NODE_ID:-single}"
REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

if [ "$NODE_ID" = "single" ]; then
    CONFIG_PATH="${REPO_DIR}/config/qdrant/single_node.yaml"
else
    CONFIG_PATH="${REPO_DIR}/config/qdrant/node${NODE_ID}.yaml"
fi

if [ ! -f "$CONFIG_PATH" ]; then
    echo "ERROR: Config not found: $CONFIG_PATH"
    exit 1
fi

echo "==> Downloading Qdrant ${QDRANT_VERSION} ..."
URL="https://github.com/qdrant/qdrant/releases/download/${QDRANT_VERSION}/qdrant-x86_64-unknown-linux-musl.tar.gz"
wget -q --show-progress "$URL" -O /tmp/qdrant.tar.gz

echo "==> Installing binary to ${INSTALL_DIR}/qdrant ..."
tar -xzf /tmp/qdrant.tar.gz -C /tmp/
sudo install -m 755 /tmp/qdrant "${INSTALL_DIR}/qdrant"
rm -f /tmp/qdrant.tar.gz /tmp/qdrant

echo "==> Writing systemd unit /etc/systemd/system/qdrant.service ..."
sudo tee /etc/systemd/system/qdrant.service > /dev/null <<EOF
[Unit]
Description=Qdrant vector database (node ${NODE_ID})
After=network.target

[Service]
Type=simple
ExecStart=${INSTALL_DIR}/qdrant --config-path ${CONFIG_PATH}
Restart=on-failure
RestartSec=5
LimitNOFILE=65536

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable qdrant
sudo systemctl restart qdrant

echo "==> Waiting for Qdrant to start ..."
for i in $(seq 1 20); do
    if curl -sf http://localhost:6333/readyz > /dev/null 2>&1; then
        echo "==> Qdrant is healthy."
        break
    fi
    sleep 1
done

curl -s http://localhost:6333/health
echo ""
echo "==> Done. Config: ${CONFIG_PATH}"
