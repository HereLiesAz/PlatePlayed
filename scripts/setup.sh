#!/usr/bin/env bash
# Quick local setup for PlatePlayed.
set -euo pipefail

cd "$(dirname "$0")/.."

echo "==> Creating virtual environment (.venv)"
python3 -m venv .venv
# shellcheck disable=SC1091
source .venv/bin/activate

echo "==> Installing core dependencies"
pip install --upgrade pip
pip install -r requirements.txt

echo "==> Installing PlatePlayed (editable)"
pip install -e .

if [ "${1:-}" = "--with-ml" ]; then
    echo "==> Installing ML engine (fast-alpr, onnxruntime)"
    pip install -r requirements-ml.txt
else
    echo "==> Skipping ML engine. Run with --with-ml to enable real plate detection."
    echo "    (Without it, the pipeline uses the no-op stub detector.)"
fi

if [ ! -f config.yaml ]; then
    cp config.example.yaml config.yaml
    echo "==> Created config.yaml from example. Edit it to add your streams."
fi

echo "==> Initializing database"
plateplayed init-db -c config.yaml

cat <<'EOF'

Setup complete. Next steps:
  source .venv/bin/activate
  plateplayed run            # start watching streams + logging plates
  plateplayed serve          # open the dashboard at http://127.0.0.1:8000
EOF
