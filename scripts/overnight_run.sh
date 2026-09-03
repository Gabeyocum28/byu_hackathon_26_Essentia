#!/usr/bin/env bash
#
# Unattended overnight corpus growth. Crawl wider, analyze what the crawl
# finds, and push the result to Cloud Run every few hours.
#
#   ./scripts/overnight_run.sh              # runs until killed
#   ./scripts/overnight_run.sh 18           # stops after 18 hours
#   tail -f ~/.essentia-run/supervisor.log  # watch it
#
# Three things this exists to survive, all of which happened today:
#
#   * essentia silently becoming an empty package. A file-sync collision
#     (Box/iCloud) left a "pytools 2" folder where the module should be, and
#     `import essentia` then succeeds as a NAMESPACE package -- no error, just
#     no algorithms. Unattended, that turns into eight wasted hours. So the
#     import is verified before every batch and repaired if broken.
#   * the analyzer exiting when it drains the queue, while the crawler is
#     still finding more. Looping it re-reads corpus_candidates.json each
#     time, which is how new crawl output gets picked up.
#   * the crawler dying on a Deezer quota wobble and nobody noticing.
#
# Analysis is resumable by design -- anything already stored at the current
# FEATURES_VERSION is skipped -- so restarting a batch costs nothing.

set -uo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# Deliberately outside Documents/: a 464 MB deploy folder inside a synced
# directory is what corrupts installs, and it would be re-uploaded on every
# change besides.
WORK="$HOME/.essentia-run"
DEPLOY="$WORK/deploy"
LOG="$WORK/supervisor.log"

ESSENTIA_PIN="essentia-tensorflow==2.1b6.dev1389"
GCP_PROJECT="decisive-scion-488906-h8"
SERVICE="essentia-server"
REGION="us-central1"

BATCH=4000              # tracks per analyzer invocation

# Six, not the default cpu_count-1 (nine). The run is download-bound at ~1.6
# tracks/s and analysis costs ~2.5 s/track, so ~4 workers saturate it; the
# rest idle while each holds its own EffNet graph (~500 MB). Trimming them
# buys back memory, which is the scarce resource here -- Redis is heading to
# ~8 GB of the machine's 16, and every RDB bgsave forks on top of that.
WORKERS=6
DEPLOY_EVERY=$((6*3600))  # push a fresh corpus to Cloud Run this often
MAX_HOURS="${1:-0}"       # 0 = run until killed

mkdir -p "$WORK"
cd "$REPO"

log() { printf '%s  %s\n' "$(date '+%H:%M:%S')" "$*" | tee -a "$LOG"; }

analyzed() { redis-cli scard corpus:ids 2>/dev/null || echo 0; }
candidates() { python3 -c "import json;print(len(json.load(open('corpus_candidates.json'))))" 2>/dev/null || echo 0; }

ensure_essentia() {
  if ! uv run --extra analysis python -c "import essentia.standard" >/dev/null 2>&1; then
    log "!! essentia is broken (empty namespace package) -- reinstalling"
    uv pip install --force-reinstall "$ESSENTIA_PIN" >>"$LOG" 2>&1
    if uv run --extra analysis python -c "import essentia.standard" >/dev/null 2>&1; then
      log "   essentia repaired"
    else
      log "   REPAIR FAILED -- analysis cannot run, see $LOG"
      return 1
    fi
  fi
  return 0
}

ensure_crawler() {
  if ! pgrep -f "crawl_breadth.py" >/dev/null; then
    log "crawler not running -- starting it"
    nohup uv run --extra dev python -u scripts/crawl_breadth.py \
        --per-genre 8000 --hops 4 --max-per-artist 2 --related 40 \
        >>"$WORK/crawl.log" 2>&1 &
  fi
}

deploy() {
  log "=== exporting snapshot and deploying ($(analyzed) tracks) ==="
  if ! PYTHONPATH=src uv run --extra dev python scripts/export_snapshot.py \
        --out "$WORK/corpus_snapshot" >>"$LOG" 2>&1; then
    log "    export failed -- keeping the live server as it is"; return 1
  fi
  mkdir -p "$DEPLOY"
  rsync -a --delete "$REPO/src/" "$DEPLOY/src/"
  rsync -a --delete "$REPO/contract/" "$DEPLOY/contract/"
  mkdir -p "$DEPLOY/scripts" && cp "$REPO/scripts/fetch_models.py" "$DEPLOY/scripts/"
  rsync -a --delete "$WORK/corpus_snapshot/" "$DEPLOY/corpus_snapshot/"
  cp "$WORK/Dockerfile" "$DEPLOY/Dockerfile" 2>/dev/null
  find "$DEPLOY" -name __pycache__ -type d -exec rm -rf {} + 2>/dev/null
  if (cd "$DEPLOY" && gcloud run deploy "$SERVICE" --source . --region "$REGION" \
        --project "$GCP_PROJECT" --allow-unauthenticated --memory 4Gi --cpu 2 \
        --timeout 300 --min-instances 1 --max-instances 3 --port 8080 --quiet \
        >>"$LOG" 2>&1); then
    log "    deployed -- server now serves $(analyzed) tracks"
  else
    log "    deploy FAILED (see $LOG) -- old revision still serving, will retry"
  fi
}

START=$(date +%s); LAST_DEPLOY=$START
log "=== overnight run starting: $(analyzed) analyzed, $(candidates) candidates ==="
[ "$MAX_HOURS" != "0" ] && log "will stop after ${MAX_HOURS}h"

while true; do
  NOW=$(date +%s); ELAPSED=$((NOW-START))
  if [ "$MAX_HOURS" != "0" ] && [ "$ELAPSED" -ge $((MAX_HOURS*3600)) ]; then
    log "=== time limit reached ==="; deploy; break
  fi

  ensure_crawler
  if ensure_essentia; then
    BEFORE=$(analyzed)
    PYTHONPATH=src uv run --extra analysis --extra dev python -u \
        scripts/analyze_corpus.py "$BATCH" --workers "$WORKERS" >>"$WORK/analyze.log" 2>&1
    AFTER=$(analyzed)
    log "batch: +$((AFTER-BEFORE)) -> $AFTER analyzed, $(candidates) candidates, ${ELAPSED}s elapsed"
    # Queue drained and the crawler has not caught up yet: idle briefly rather
    # than spinning on an empty candidate list.
    [ "$((AFTER-BEFORE))" -lt 5 ] && { log "queue dry -- waiting for the crawler"; sleep 120; }
  else
    sleep 300
  fi

  if [ $(( $(date +%s) - LAST_DEPLOY )) -ge "$DEPLOY_EVERY" ]; then
    deploy; LAST_DEPLOY=$(date +%s)
  fi
done
log "=== finished: $(analyzed) tracks analyzed ==="
