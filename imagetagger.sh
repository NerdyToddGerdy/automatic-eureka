#!/usr/bin/env bash
# Controls the ImageTagger (Image Vault) pywebview desktop app.
# Safe to run repeatedly - detects an already-running instance and
# avoids spawning duplicates or leaving orphaned backends behind.
#
# Prefers the packaged app (dist/Image Vault.app); falls back to the
# dev entry point (python3 desktop.py) when no build is present.
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG_FILE="/tmp/imagetagger_desktop.log"
PORT=5000
APP_BUNDLE="$PROJECT_DIR/dist/Image Vault.app"
# Matches both the packaged PyInstaller binary and the dev entry point so a
# running instance is found regardless of how it was launched.
DESKTOP_PATTERN="Image Vault.app/Contents/MacOS/Image Vault|[d]esktop\.py"

cd "$PROJECT_DIR"

usage() {
  cat <<EOF
Usage: $(basename "$0") [--stop|-h|--help]

  (no flags)   Start ImageTagger if it isn't already running.
  --stop       Stop ImageTagger (closes the window and kills the backend).
  -h, --help   Show this help.
EOF
}

backend_up() {
  curl -sf "http://127.0.0.1:${PORT}/api/version" >/dev/null 2>&1
}

desktop_pids() {
  pgrep -f "$DESKTOP_PATTERN" 2>/dev/null || true
}

port_pids() {
  lsof -ti "tcp:${PORT}" -sTCP:LISTEN 2>/dev/null || true
}

launch_app() {
  if [ -d "$APP_BUNDLE" ]; then
    echo "Launching packaged app: $APP_BUNDLE"
    open "$APP_BUNDLE"
  else
    echo "No packaged app found - starting dev mode (python3 desktop.py)..."
    nohup python3 desktop.py > "$LOG_FILE" 2>&1 &
    disown
  fi
}

start_imagetagger() {
  local existing_desktop
  existing_desktop="$(desktop_pids)"

  if [ -n "$existing_desktop" ] && backend_up; then
    echo "ImageTagger is already running (PID(s): $existing_desktop) at http://127.0.0.1:${PORT}"
    return 0
  fi

  # Stale window with a dead backend - close it before relaunching.
  if [ -n "$existing_desktop" ]; then
    echo "Found a stale window with no live backend. Closing it..."
    for pid in $existing_desktop; do
      kill -TERM "$pid" 2>/dev/null || true
    done
    for i in $(seq 1 10); do
      [ -z "$(desktop_pids)" ] && break
      sleep 0.5
    done
    for pid in $(desktop_pids); do
      kill -9 "$pid" 2>/dev/null || true
    done
  fi

  # Anything else (e.g. a standalone `python3 app.py`) squatting on the port.
  local stale_port_pids
  stale_port_pids="$(port_pids)"
  if [ -n "$stale_port_pids" ]; then
    echo "Port ${PORT} is held by another process. Freeing it..."
    for pid in $stale_port_pids; do
      kill -TERM "$pid" 2>/dev/null || true
    done
    sleep 1
  fi

  echo "Starting ImageTagger..."
  launch_app

  for i in $(seq 1 30); do
    if backend_up; then
      echo "ImageTagger is up at http://127.0.0.1:${PORT}"
      return 0
    fi
    sleep 0.5
  done

  echo "ImageTagger did not come up within 15s. Check $LOG_FILE" >&2
  return 1
}

stop_imagetagger() {
  local desktop_to_kill backend_to_kill
  desktop_to_kill="$(desktop_pids)"
  backend_to_kill="$(port_pids)"

  if [ -z "$desktop_to_kill" ] && [ -z "$backend_to_kill" ]; then
    echo "ImageTagger is not running."
    return 0
  fi

  if [ -n "$desktop_to_kill" ]; then
    echo "Stopping desktop app (PID(s): $desktop_to_kill)..."
    for pid in $desktop_to_kill; do kill -TERM "$pid" 2>/dev/null || true; done
  fi

  if [ -n "$backend_to_kill" ]; then
    echo "Stopping backend on port ${PORT} (PID(s): $backend_to_kill)..."
    for pid in $backend_to_kill; do kill -TERM "$pid" 2>/dev/null || true; done
  fi

  for i in $(seq 1 10); do
    [ -z "$(desktop_pids)" ] && [ -z "$(port_pids)" ] && break
    sleep 0.5
  done

  # Force-kill anything still hanging around.
  for pid in $(desktop_pids); do kill -9 "$pid" 2>/dev/null || true; done
  for pid in $(port_pids); do kill -9 "$pid" 2>/dev/null || true; done

  echo "ImageTagger stopped."
}

case "${1:-}" in
  -h|--help)
    usage
    ;;
  --stop)
    stop_imagetagger
    ;;
  "")
    start_imagetagger
    ;;
  *)
    echo "Unknown option: $1" >&2
    usage >&2
    exit 1
    ;;
esac
