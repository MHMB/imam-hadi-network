#!/usr/bin/env bash
# Pull the latest images and (re)start the production stack.
#
# Run on the OVH host from /opt/imamhadi/compose (or via `ssh personal ...`
# from a developer laptop — see Makefile deploy target).

set -euo pipefail

cd "$(dirname "$0")/.."

if [ ! -f .env ]; then
  echo "FATAL: .env missing; copy .env.example and fill it." >&2
  exit 1
fi

# shellcheck disable=SC1091
set -a; . ./.env; set +a

# Login if a GHCR_TOKEN is supplied (and we are not already logged in).
if [ -n "${GHCR_TOKEN:-}" ]; then
  echo "$GHCR_TOKEN" | docker login ghcr.io -u "$GH_OWNER" --password-stdin >/dev/null
fi

docker compose -f docker-compose.prod.yml pull
docker compose -f docker-compose.prod.yml up -d --remove-orphans
docker compose -f docker-compose.prod.yml ps
