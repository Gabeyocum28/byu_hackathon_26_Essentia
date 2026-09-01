#!/bin/bash
# Essencia embed worker + SSH tunnel, supervised by launchd.
#
# The Oracle VM is ARM and cannot run essentia, so the embed/attribution work
# happens on a Mac: this opens an SSH tunnel to the VM's Redis and runs the
# worker against it. If either the tunnel or the worker dies, this script
# exits and launchd restarts the pair.
#
# Installed copy (what launchd actually runs) lives at
#   ~/Library/Application Support/essencia/embed_worker_run.sh
# loaded by ~/Library/LaunchAgents/com.essencia.embed-worker.plist.
# launchd agents cannot read ~/Desktop, so the installed copy runs against its
# own clone rather than a Desktop checkout. After editing this file, reinstall:
#   cp scripts/embed_worker_run.sh "$HOME/Library/Application Support/essencia/"
#   launchctl kickstart -k gui/$(id -u)/com.essencia.embed-worker
set -u

REPO="${ESSENCIA_REPO:-$HOME/Library/Application Support/essencia/repo}"
KEY="${ESSENCIA_SSH_KEY:-$HOME/.ssh/temprovio_agents.key}"
PYTHON="${ESSENCIA_PYTHON:-$HOME/.pyenv/versions/3.11.9/bin/python3}"
VM_HOST="${ESSENCIA_VM_HOST:-opc@163.192.48.114}"
PORT="${ESSENCIA_REDIS_PORT:-16379}"

# Clear any stale tunnel we started earlier (a dead ssh can hold the port).
pkill -f "ssh .* -L ${PORT}:localhost:6379" 2>/dev/null
sleep 1

ssh -i "$KEY" -N \
    -o ExitOnForwardFailure=yes \
    -o ServerAliveInterval=30 \
    -o ServerAliveCountMax=3 \
    -o ConnectTimeout=10 \
    -o BatchMode=yes \
    -L ${PORT}:localhost:6379 \
    "$VM_HOST" &
TUNNEL_PID=$!
trap 'kill $TUNNEL_PID 2>/dev/null' EXIT

# Give the tunnel a moment; if ssh already died (no network), exit and let
# launchd retry after its throttle interval.
sleep 2
kill -0 $TUNNEL_PID 2>/dev/null || exit 1

cd "$REPO"
# Stay current with main; tolerate being offline.
git pull --ff-only -q 2>/dev/null || true
REDIS_URL="redis://localhost:${PORT}/0" PYTHONPATH=src "$PYTHON" scripts/embed_worker.py &
WORKER_PID=$!
trap 'kill $TUNNEL_PID $WORKER_PID 2>/dev/null' EXIT

# The worker retries Redis errors forever, so it will NOT exit when the tunnel
# drops -- it just spins on "Connection refused". Watch both PIDs and exit as
# soon as either one dies so launchd restarts the pair.
while true; do
    if ! kill -0 $TUNNEL_PID 2>/dev/null; then
        echo "[wrapper] ssh tunnel died; restarting pair"
        kill $WORKER_PID 2>/dev/null
        exit 1
    fi
    if ! kill -0 $WORKER_PID 2>/dev/null; then
        echo "[wrapper] worker died; restarting pair"
        kill $TUNNEL_PID 2>/dev/null
        exit 1
    fi
    sleep 5
done
