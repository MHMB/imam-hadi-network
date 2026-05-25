# syntax=docker/dockerfile:1.7
# ---- Build stage ----
FROM python:3.12-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_LINK_MODE=copy \
    UV_COMPILE_BYTECODE=1

# uv binary
COPY --from=ghcr.io/astral-sh/uv:0.5.7 /uv /uvx /usr/local/bin/

WORKDIR /app

# Install deps first for layer caching.  WORKDIR=/app so the venv's script
# shebangs are written as #!/app/.venv/bin/python — same path the runtime
# stage uses, so we don't need to rewrite shebangs after the COPY --from.
COPY pyproject.toml uv.lock* ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --no-dev --frozen --no-install-project || uv sync --no-dev --no-install-project

# Copy app + readme (hatchling reads README.md at install time)
COPY src ./src
COPY alembic.ini ./alembic.ini
COPY README.md ./README.md

RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --no-dev --frozen || uv sync --no-dev

# ---- Runtime stage ----
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/app/.venv/bin:${PATH}"

# Non-root user
RUN groupadd --system app && useradd --system --gid app --home-dir /app app
WORKDIR /app

# Copy the whole built tree (venv has shebangs pinned to /app/.venv/...).
COPY --from=builder --chown=app:app /app /app

USER app

EXPOSE 8000

# Entrypoint: apply migrations, then uvicorn
COPY --chown=app:app docker-entrypoint.sh /app/docker-entrypoint.sh
ENTRYPOINT ["/app/docker-entrypoint.sh"]
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
