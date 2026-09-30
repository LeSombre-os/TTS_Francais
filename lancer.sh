#!/bin/bash
# TTS Français local — double-clic via "TTS Français.desktop", ou ./lancer.sh
# ./lancer.sh --cpu  →  force CPU (même sans CG)
# ./lancer.sh --gpu  →  force GPU (échoue si pas de CG)
# ./lancer.sh stop   →  arrête le serveur
cd "$(dirname "$0")"
PORT=8901
URL="http://127.0.0.1:$PORT"

if [ "$1" = "stop" ]; then
  pkill -f "uvicorn app:app.*$PORT" 2>/dev/null
  echo "Serveur arrêté."
  exit 0
fi

# 2e double-clic : réutilise le serveur déjà lancé
if curl -s -o /dev/null --max-time 2 "$URL/api/status" 2>/dev/null; then
  echo "Déjà en cours : $URL"
  (xdg-open "$URL" >/dev/null 2>&1) &
  exit 0
fi

MODE="auto"
[ "$1" = "--cpu" ] && MODE="cpu"
[ "$1" = "--gpu" ] && MODE="gpu"

PY="$HOME/.venvs/tts/bin/python"
if [ "$MODE" = "cpu" ]; then
  :  # venv CPU dans tous les cas
elif [ -x "$HOME/.venvs/tts-rocm/bin/python" ] \
  && [ "$MODE" = "gpu" -o "$MODE" = "auto" ] \
  && "$HOME/.venvs/tts-rocm/bin/python" -c "import torch; assert torch.cuda.is_available()" 2>/dev/null; then
  PY="$HOME/.venvs/tts-rocm/bin/python"
  echo "GPU détectée : mode accéléré."
elif [ "$MODE" = "gpu" ]; then
  echo "Pas de GPU utilisable."
  exit 1
fi
[ -x "$PY" ] || PY=python3
export TTS_DEVICE="$MODE"
# ouvre le navigateur une fois le serveur démarré (le modèle charge en différé)
(sleep 10; xdg-open "$URL" >/dev/null 2>&1) &
exec "$PY" -m uvicorn app:app --host 127.0.0.1 --port "$PORT"
