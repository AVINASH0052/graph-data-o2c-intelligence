#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT_DIR"

BACKEND_ENV_FILE="backend/.env"
HEALTH_URL="http://localhost:8000/health"
FRONTEND_URL="http://localhost"

if ! command -v docker >/dev/null 2>&1; then
  echo "Error: docker is not installed or not in PATH"
  exit 1
fi

if ! docker compose version >/dev/null 2>&1; then
  echo "Error: docker compose is not available"
  exit 1
fi

if [[ ! -f "$BACKEND_ENV_FILE" ]]; then
  echo "Error: $BACKEND_ENV_FILE is missing"
  echo "Create it from backend/.env.example and set NVIDIA_API_KEY."
  exit 1
fi

echo "Starting backend + frontend with Docker Compose..."
docker compose up --build -d

echo "Waiting for backend health..."
max_attempts=120
attempt=1
until curl -fsS "$HEALTH_URL" >/dev/null 2>&1; do
  if (( attempt >= max_attempts )); then
    echo "Backend did not become healthy in time."
    echo "Check logs with: docker compose logs backend --tail=200"
    exit 1
  fi

  if (( attempt % 10 == 0 )); then
    echo "Still waiting... (attempt $attempt/$max_attempts)"
  fi

  sleep 2
  ((attempt++))
done

echo ""
echo "Services are up."
echo "Frontend: $FRONTEND_URL"
echo "Backend health: $HEALTH_URL"
echo "Graph stats: http://localhost:8000/api/graph/stats"

echo ""
echo "Quick checks:"
echo "  curl -sS $HEALTH_URL"
echo "  curl -sS http://localhost:8000/api/graph/stats"

echo ""
echo "Follow logs: docker compose logs -f"
echo "Stop all: docker compose down"
