#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"

# ─── Colors ───────────────────────────────────────────────────────────────────
RED='\033[0;31m'; GREEN='\033[0;32m'; CYAN='\033[0;36m'; DIM='\033[2m'; RESET='\033[0m'
info()  { echo -e "${CYAN}▸${RESET} $*"; }
ok()    { echo -e "${GREEN}✓${RESET} $*"; }
err()   { echo -e "${RED}✗${RESET} $*" >&2; }

# ─── Usage ────────────────────────────────────────────────────────────────────
usage() {
  cat <<EOF
Usage: ./start.sh [MODE]

Modes:
  dev       Dashboard runs locally (Vite HMR), everything else in Docker.
            Skip dashboard image build — instant frontend iteration.
  docker    Full Docker Compose — all services containerized (includes dashboard build).
  stop      Stop all services (local processes + all ants-* / nest containers).

Examples:
  ./start.sh          # dev mode (default)
  ./start.sh docker   # Production-like
  ./start.sh stop     # Tear it all down
EOF
  exit 1
}

MODE="${1:-dev}"

# ─── Shared ───────────────────────────────────────────────────────────────────
PROJECT_ROOT="$(pwd)"
DATA_DIR="$PROJECT_ROOT/data"
PIDFILE_DIR="$DATA_DIR/.pids"

mkdir -p "$DATA_DIR/volumes" "$DATA_DIR/mysql" "$DATA_DIR/minio" "$PIDFILE_DIR"

kill_pid_file() {
  local f="$1"
  if [[ -f "$f" ]]; then
    local pid; pid=$(<"$f")
    if kill -0 "$pid" 2>/dev/null; then
      kill "$pid" 2>/dev/null || true
      info "Stopped PID $pid ($(basename "$f" .pid))"
    fi
    rm -f "$f"
  fi
}

# ─── stop ─────────────────────────────────────────────────────────────────────
if [[ "$MODE" == "stop" ]]; then
  info "Stopping local processes..."
  for f in "$PIDFILE_DIR"/*.pid; do
    [[ -f "$f" ]] && kill_pid_file "$f"
  done
  info "Stopping all ants/nest containers..."
  docker ps -q --filter "name=ants-" 2>/dev/null | xargs -r docker stop 2>/dev/null || true
  docker ps -q -a --filter "name=ants-" 2>/dev/null | xargs -r docker rm 2>/dev/null || true
  docker ps -q --filter "name=nest" 2>/dev/null | xargs -r docker stop 2>/dev/null || true
  docker ps -q -a --filter "name=nest" 2>/dev/null | xargs -r docker rm 2>/dev/null || true
  info "Docker compose down..."
  docker compose down 2>/dev/null || true
  ok "All stopped."
  exit 0
fi

# ─── docker mode ──────────────────────────────────────────────────────────────
if [[ "$MODE" == "docker" ]]; then
  info "Building and starting all services via Docker Compose..."
  docker compose up -d --build
  echo ""
  ok "All services running:"
  echo -e "   Nest API        ${DIM}http://localhost:22000${RESET}"
  echo -e "   Dashboard       ${DIM}http://localhost:22002${RESET}"
  echo -e "   Queen           ${DIM}http://localhost:22100${RESET}"
  echo -e "   MinIO Console   ${DIM}http://localhost:22004${RESET}"
  echo -e "   MySQL           ${DIM}localhost:22005${RESET}"
  exit 0
fi

# ─── dev mode ─────────────────────────────────────────────────────────────────
if [[ "$MODE" != "dev" ]]; then
  err "Unknown mode: $MODE"
  usage
fi

# 1) Backend services in Docker (nest, queen, mysql, minio) — skip dashboard
info "Starting backend services (nest + queen + infra)..."
docker compose up -d --build nest queen mysql minio
ok "Nest, Queen, MySQL, MinIO containers up"

# 2) Wait for MySQL
info "Waiting for MySQL..."
for i in $(seq 1 30); do
  if docker exec ants-mysql mysqladmin ping -h localhost -uants -pchangeme --silent 2>/dev/null; then
    break
  fi
  sleep 1
done
ok "MySQL is healthy"

# 3) Dashboard — local Vite dev + Node backend (no Docker build)
kill_pid_file "$PIDFILE_DIR/dashboard-api.pid"
kill_pid_file "$PIDFILE_DIR/dashboard-vite.pid"

cd "$PROJECT_ROOT/nest/dashboard"

if [[ ! -d "node_modules" ]]; then
  info "Installing dashboard dependencies..."
  npm install --legacy-peer-deps -q
fi

export PORT=22012
export MYSQL_HOST=127.0.0.1
export MYSQL_PORT=22005
export MYSQL_USER=ants
export MYSQL_PASSWORD=changeme
export MYSQL_DATABASE=ants
export MINIO_ENDPOINT=127.0.0.1
export MINIO_PORT=22003
export MINIO_ACCESS_KEY=ants
export MINIO_SECRET_KEY=antspassword

info "Starting Dashboard API on :22012..."
node server/index.cjs > "$DATA_DIR/dashboard-api.log" 2>&1 &
echo $! > "$PIDFILE_DIR/dashboard-api.pid"
ok "Dashboard API PID $!"

export VITE_NEST_URL=http://localhost:22000

info "Starting Vite dev server on :22002..."
npx vite --port 22002 --strictPort > "$DATA_DIR/dashboard-vite.log" 2>&1 &
echo $! > "$PIDFILE_DIR/dashboard-vite.pid"
ok "Vite dev server PID $!"

cd "$PROJECT_ROOT"

echo ""
ok "Dev mode running"
echo ""
echo -e "   ${GREEN}→  http://localhost:22002${RESET}"
echo ""
echo -e "   Nest API          ${DIM}http://localhost:22000${RESET}"
echo -e "   Queen             ${DIM}http://localhost:22100${RESET}"
echo -e "   MinIO Console     ${DIM}http://localhost:22004${RESET}"
echo -e "   MySQL             ${DIM}localhost:22005${RESET}"
echo -e "   Logs              ${DIM}$DATA_DIR/*.log${RESET}"
echo -e "   Stop              ${DIM}./start.sh stop${RESET}"
