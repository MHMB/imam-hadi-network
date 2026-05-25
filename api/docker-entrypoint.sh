#!/bin/sh
set -e

# Apply Alembic migrations before serving traffic.
echo "[entrypoint] alembic upgrade head"
alembic upgrade head

echo "[entrypoint] starting: $*"
exec "$@"
