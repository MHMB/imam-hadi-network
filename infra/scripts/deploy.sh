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

# IMPORTANT: do NOT source .env via bash — values like a bcrypt'd
# BASIC_AUTH_USERS contain literal $$, $2, etc. that bash would expand
# (e.g. $$ → PID).  docker compose reads .env natively without shell
# expansion, which is what we want.  Only pull out GHCR_* for `docker
# login` by grepping the raw file.
GH_OWNER=$(awk -F= '/^GH_OWNER=/{print $2}' .env)
GHCR_TOKEN=$(awk -F= '/^GHCR_TOKEN=/{print $2}' .env)

# Login if a GHCR_TOKEN is supplied (and we are not already logged in).
if [ -n "${GHCR_TOKEN}" ] && [ -n "${GH_OWNER}" ]; then
  echo "$GHCR_TOKEN" | docker login ghcr.io -u "$GH_OWNER" --password-stdin >/dev/null
fi

docker compose -f docker-compose.prod.yml pull
docker compose -f docker-compose.prod.yml up -d --remove-orphans
docker compose -f docker-compose.prod.yml ps
