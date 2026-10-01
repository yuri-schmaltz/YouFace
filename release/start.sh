#!/bin/bash
# Pinokio launcher entrypoint (R15 of gauntlet — multi-profile support).
#
# Usage:
#   ./start.sh                   # auto-detect GPU
#   ./start.sh --profile nvidia  # force NVIDIA compose profile
#   ./start.sh --profile amd     # force AMD compose profile
#   ./start.sh --profile cpu     # force CPU-only profile
#
# The script detects the available GPU by probing nvidia-smi, rocm-smi,
# and /dev/dri; falls back to CPU when nothing is found.

set -e

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROFILE="auto"

# Parse args
while [[ $# -gt 0 ]]; do
    case "$1" in
        --profile)
            PROFILE="$2"
            shift 2
            ;;
        --help|-h)
            echo "Usage: $0 [--profile nvidia|amd|cpu|auto]"
            exit 0
            ;;
        *)
            echo "Unknown arg: $1"
            exit 1
            ;;
    esac
done

# Auto-detect when --profile wasn't passed
if [[ "$PROFILE" == "auto" ]]; then
    if command -v nvidia-smi >/dev/null 2>&1 && nvidia-smi >/dev/null 2>&1; then
        PROFILE="nvidia"
    elif [[ -d /dev/dri ]] && command -v rocm-smi >/dev/null 2>&1; then
        PROFILE="amd"
    else
        PROFILE="cpu"
    fi
    echo "[start.sh] Auto-detected profile: $PROFILE"
fi

# Iniciar o backend no segundo plano
"$DIR/youface-app" --profile "$PROFILE" &
BACKEND_PID=$!

echo "Inicializando o YouFace local (profile=$PROFILE)..."
# Aguardar inicializacao
PORT=8000
for i in {1..20}; do
    for p in {8000..8020}; do
        if curl -s http://localhost:$p/api/config > /dev/null; then
            PORT=$p
            break 2
        fi
    done
    sleep 0.5
done

URL="http://localhost:${PORT}/"
echo "Abrindo o navegador em $URL"

if which xdg-open > /dev/null; then
    xdg-open "$URL"
elif which gnome-open > /dev/null; then
    gnome-open "$URL"
elif which kde-open > /dev/null; then
    kde-open "$URL"
else
    echo "Abra o navegador em: $URL"
fi

# Aguardar finalizacao do backend
wait $BACKEND_PID
