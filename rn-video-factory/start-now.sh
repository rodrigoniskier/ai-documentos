#!/usr/bin/env sh
set -eu

node dist/app.js &
server_pid=$!

shutdown() {
  kill -TERM "$server_pid" 2>/dev/null || true
  wait "$server_pid" 2>/dev/null || true
}
trap shutdown INT TERM

(
  sleep 8
  marker="${DATA_DIR:-/data}/first-video-generated"
  if [ ! -f "$marker" ]; then
    echo "Iniciando a produção imediata do primeiro vídeo..."
    if node dist/app.js --generate; then
      date -u +%FT%TZ > "$marker"
      echo "Primeiro vídeo concluído e disponível no painel."
    else
      echo "A produção imediata falhou; o próximo reinício tentará novamente." >&2
    fi
  fi
) &

wait "$server_pid"
