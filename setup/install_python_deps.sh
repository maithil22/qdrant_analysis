#!/bin/bash
# Create virtualenv and install Python dependencies.
# Run from repo root: bash setup/install_python_deps.sh
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_DIR"

echo "==> Creating .venv ..."
python3 -m venv .venv

echo "==> Installing dependencies ..."
.venv/bin/pip install --upgrade pip
.venv/bin/pip install -e ".[dev]"

echo "==> Pinning requirements.txt ..."
.venv/bin/pip freeze > requirements.txt

echo "==> Done. Activate with: source .venv/bin/activate"
