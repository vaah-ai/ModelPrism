#!/usr/bin/env bash
# ────────────────────────────────────────────────────────────────────
# ModelPrism — Local Development Launcher
# Starts the Nuxt frontend and FastAPI backend with fixed ports.
#
# Fixed ports:
#   Nuxt (Frontend)          → 3020
#   FastAPI (Backend API)    → 3021
#
# If any process is already running on these ports, it will be killed
# before the service starts.
#
# Usage:
#   bash start.sh            → start both services
#   bash start.sh --stop     → stop both services
#   bash start.sh --status   → check which services are running
# ────────────────────────────────────────────────────────────────────
set -uo pipefail

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT_DIR"

# Fixed ports
NUXT_PORT=3020
API_PORT=3021

# Paths
FRONTEND_DIR="$ROOT_DIR/frontend"
BACKEND_DIR="$ROOT_DIR/backend"
NUXT_LOG="/tmp/modelprism-nuxt.log"
API_LOG="/tmp/modelprism-api.log"
PID_FILE="/tmp/modelprism-pids"

# ANSI colours
GREEN='\033[0;32m'; CYAN='\033[0;36m'; YELLOW='\033[1;33m'; RED='\033[0;31m'; NC='\033[0m'
info()  { printf "${CYAN}[INFO]${NC}  %s\n" "$*"; }
ok()    { printf "${GREEN}[OK]${NC}    %s\n" "$*"; }
warn()  { printf "${YELLOW}[WARN]${NC}  %s\n" "$*"; }
err()   { printf "${RED}[ERR]${NC}   %s\n" "$*"; }

# ── Pre-flight checks ─────────────────────────────────────────────
check_deps() {
  local missing=0
  for cmd in npm uv; do
    if ! command -v "$cmd" &>/dev/null; then
      err "$cmd is not installed — install it first"
      missing=1
    fi
  done
  if [ "$missing" -eq 1 ]; then exit 1; fi
}

# ── Stop ───────────────────────────────────────────────────────────
stop_services() {
  warn "Shutting down services …"

  # Kill by PID file
  if [ -f "$PID_FILE" ]; then
    # shellcheck disable=SC1091
    source "$PID_FILE"
    [ -n "${NPM_PID:-}" ] && kill "$NPM_PID" 2>/dev/null || true
    [ -n "${UVICORN_PID:-}" ] && kill "$UVICORN_PID" 2>/dev/null || true
  fi

  # Kill by port (catches processes started outside start.sh)
  for p in "$NUXT_PORT" "$API_PORT"; do
    local pids
    pids=$(lsof -ti :"$p" 2>/dev/null || true)
    while IFS= read -r pid; do
      [ -z "$pid" ] && continue
      local pname
      pname=$(ps -p "$pid" -o comm= 2>/dev/null || echo "")
      pbase_lower=$(basename "$pname" 2>/dev/null | tr '[:upper:]' '[:lower:]')
      case "$pbase_lower" in
        node|python|uvicorn|nuxt) kill "$pid" 2>/dev/null || true ;;
        *) : ;;
      esac
    done <<< "$pids"
  done

  sleep 2
  # Second pass: SIGKILL survivors
  for p in "$NUXT_PORT" "$API_PORT"; do
    local pids
    pids=$(lsof -ti :"$p" 2>/dev/null || true)
    while IFS= read -r pid; do
      [ -z "$pid" ] && continue
      local pname
      pname=$(ps -p "$pid" -o comm= 2>/dev/null || echo "")
      pbase_lower=$(basename "$pname" 2>/dev/null | tr '[:upper:]' '[:lower:]')
      case "$pbase_lower" in
        node|python|uvicorn|nuxt) kill -9 "$pid" 2>/dev/null || true ;;
        *) : ;;
      esac
    done <<< "$pids"
  done

  rm -f "$PID_FILE"
  ok "All services stopped."
}

# ── Status ──────────────────────────────────────────────────────────
status() {
  echo ""
  info "═══════════════════════════════════════════════"
  info "  Service Status"
  info "═══════════════════════════════════════════════"
  echo ""

  local COL=20

  # Nuxt
  printf "  %-${COL}s " "Nuxt (Frontend)"
  if lsof -ti :"$NUXT_PORT" >/dev/null 2>&1; then
    ok "✅ http://localhost:${NUXT_PORT}"
  else
    err "❌ Not running"
  fi

  # FastAPI
  printf "  %-${COL}s " "FastAPI (Backend)"
  if lsof -ti :"$API_PORT" >/dev/null 2>&1; then
    if curl -sf "http://localhost:${API_PORT}/api/health" >/dev/null 2>&1; then
      ok "✅ http://localhost:${API_PORT}/api/health"
    else
      warn "⚠️  Port $API_PORT open but health check failed"
    fi
  else
    err "❌ Not running"
  fi

  echo ""
}

# ── Free port helper ────────────────────────────────────────────────
free_port() {
  local port=$1
  local pids
  pids=$(lsof -ti :"$port" 2>/dev/null || true)
  if [ -n "$pids" ]; then
    while IFS= read -r pid; do
      [ -z "$pid" ] && continue
      local pname
      pname=$(ps -p "$pid" -o comm= 2>/dev/null || echo "")
      pbase_lower=$(basename "$pname" 2>/dev/null | tr '[:upper:]' '[:lower:]')
      case "$pbase_lower" in
        node|python|uvicorn|nuxt) kill "$pid" 2>/dev/null || true ;;
      esac
    done <<< "$pids"
    sleep 1
    # Second pass: SIGKILL
    pids=$(lsof -ti :"$port" 2>/dev/null || true)
    while IFS= read -r pid; do
      [ -z "$pid" ] && continue
      local pname
      pname=$(ps -p "$pid" -o comm= 2>/dev/null || echo "")
      pbase_lower=$(basename "$pname" 2>/dev/null | tr '[:upper:]' '[:lower:]')
      case "$pbase_lower" in
        node|python|uvicorn|nuxt) kill -9 "$pid" 2>/dev/null || true ;;
      esac
    done <<< "$pids"
    # Wait up to 5 seconds for port to free
    for _i in $(seq 1 5); do
      if ! lsof -ti :"$port" >/dev/null 2>&1; then break; fi
      sleep 1
    done
  fi
}

# ── Start Nuxt ──────────────────────────────────────────────────────
start_nuxt() {
  free_port "$NUXT_PORT"
  info "Starting Nuxt dev server on port $NUXT_PORT …"
  rm -f "$NUXT_LOG"
  cd "$FRONTEND_DIR"
  TMPDIR=/tmp NODE_OPTIONS='--disable-warning=DEP0205' \
    PORT="$NUXT_PORT" \
    NUXT_PUBLIC_BACKEND_URL="http://localhost:${API_PORT}" \
    npx nuxt dev --port "$NUXT_PORT" > "$NUXT_LOG" 2>&1 &
  NPM_PID=$!
  cd "$ROOT_DIR"

  # Wait for Nuxt to be ready (up to 120 seconds)
  info "Waiting for Nuxt to start …"
  tail -f "$NUXT_LOG" &
  local _TAIL_PID=$!
  for i in $(seq 1 120); do
    if grep -q "http://localhost:${NUXT_PORT}" "$NUXT_LOG" 2>/dev/null; then
      kill "$_TAIL_PID" 2>/dev/null || true
      ok "Nuxt is ready (http://localhost:${NUXT_PORT})"
      return 0
    fi
    if [ "$i" -eq 120 ]; then
      kill "$_TAIL_PID" 2>/dev/null || true
      err "Nuxt startup timed out — check $NUXT_LOG for errors"
      return 1
    fi
    sleep 1
  done
}

# ── Start FastAPI ──────────────────────────────────────────────────
start_api() {
  free_port "$API_PORT"
  info "Starting FastAPI on port $API_PORT …"
  rm -f "$API_LOG"

  if [ ! -d "$BACKEND_DIR/.venv" ]; then
    info "No Python virtualenv found at backend/.venv — creating one …"
    cd "$BACKEND_DIR"
    uv sync --frozen 2>/dev/null || uv sync
    cd "$ROOT_DIR"
  fi

  cd "$BACKEND_DIR"
  CORS_ORIGINS="http://localhost:${NUXT_PORT}" \
    NUXT_PUBLIC_BACKEND_URL="http://localhost:${API_PORT}" \
    uv run uvicorn app.main:app \
    --host 0.0.0.0 --port "$API_PORT" --reload \
    --log-level warning \
    > "$API_LOG" 2>&1 &
  UVICORN_PID=$!
  cd "$ROOT_DIR"

  # Wait for FastAPI health check with a shorter timeout and DB readiness check
  info "Waiting for FastAPI to start …"
  local API_STARTED=false
  for i in $(seq 1 30); do
    if curl -sf "http://localhost:${API_PORT}/api/health" &>/dev/null; then
      ok "FastAPI is ready (http://localhost:${API_PORT})"
      API_STARTED=true
      break
    fi
    # If the api log shows a DB connection failure, warn and move on
    if grep -q "Failed to connect to database" "$API_LOG" 2>/dev/null; then
      warn "FastAPI cannot connect to PostgreSQL — check docker compose ps"
      warn "Continuing anyway — the API will keep retrying."
      API_STARTED=false
      break
    fi
    if [ "$i" -eq 30 ]; then
      warn "FastAPI health check timed out — continuing anyway"
    fi
    sleep 1
  done

  if [ "$API_STARTED" = false ]; then
    # Print tail of the API log for diagnostics
    info "Last 10 lines of API log:"
    tail -10 "$API_LOG" 2>/dev/null | sed 's/^/  /'
  fi
}

# ── Main ───────────────────────────────────────────────────────────
main() {
  check_deps
  echo ""
  info "═══════════════════════════════════════════════"
  info "  ModelPrism — Starting all services…"
  info "═══════════════════════════════════════════════"
  echo ""

  # ── 1. Docker infrastructure ──
  if lsof -i :5432 >/dev/null 2>&1; then
    ok "PostgreSQL already running (localhost:5432)"
  elif docker info &>/dev/null; then
    info "Starting PostgreSQL and Redis (Docker Compose) …"
    docker compose up -d --wait postgres redis 2>&1
    ok "PostgreSQL is ready (localhost:5432)"
    ok "Redis is ready (localhost:6379)"
  else
    warn "Docker Desktop is not running — skipping PostgreSQL and Redis"
  fi
  echo ""

  # ── 2. Nuxt ──
  start_nuxt
  echo ""

  # ── 3. Database migrations (only if DB is reachable) ──
  if lsof -ti :5432 >/dev/null 2>&1; then
    info "Running database migrations …"
    cd "$BACKEND_DIR"
    uv run alembic upgrade head 2>&1
    cd "$ROOT_DIR"
    ok "Database migrations up to date"
    echo ""
  fi

  # ── 4. FastAPI ──
  start_api
  echo ""

  # Save PIDs for --stop
  cat > "$PID_FILE" <<-PIDEOF
NPM_PID=$NPM_PID
UVICORN_PID=${UVICORN_PID:-}
PIDEOF

  # Print summary
  echo ""
  info "═══════════════════════════════════════════════"
  info "  Service URLs                                 "
  info "═══════════════════════════════════════════════"
  echo ""
  printf "  ${GREEN}Nuxt (Frontend)${NC}        →  ${CYAN}http://localhost:${NUXT_PORT}${NC}\n"
  printf "  ${GREEN}FastAPI (Backend)${NC}       →  ${CYAN}http://localhost:${API_PORT}${NC}\n"
  printf "  ${GREEN}FastAPI Docs (Swagger)${NC}   →  ${CYAN}http://localhost:${API_PORT}/api/docs${NC}\n"
  echo ""
  printf "  ${YELLOW}Log files:${NC}\n"
  printf "    Nuxt:   %s\n" "$NUXT_LOG"
  printf "    API:    %s\n" "$API_LOG"
  echo ""
  printf "  ${YELLOW}Stop:${NC}   bash %s --stop\n" "$0"
  echo ""
}

# ── Dispatch ──────────────────────────────────────────────────────
case "${1:---start}" in
  --stop)   stop_services ;;
  --status) status ;;
  --start|"")
    stop_services
    sleep 1
    main
    ;;
  *)
    echo "Usage: bash start.sh [--start|--stop|--status]"
    exit 1
    ;;
esac
