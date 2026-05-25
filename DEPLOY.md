# Deployment Runbook (Phase 1)

Target: single OVH VPS reachable as `ssh personal`.  Co-tenant with the
existing **n8n** stack — never touched by anything in this project.

Reference: [DESIGN.md §8](./DESIGN.md) for the architecture rationale,
[PLAN.md §0](./PLAN.md) for the verified server inventory.

---

## 0. Prerequisites

- DNS — pick one of:
  - **OVH default subdomain** `vps-d5fdd1dd.vps.ovh.us` — already resolves,
    works with Let's Encrypt out of the box.  Use this for first ship.
  - **Custom domain** — add an `A` record pointing at the VPS public IPv4
    (`15.204.95.254`) before bootstrapping.  Update `PUBLIC_HOST` in `.env`.
- A GitHub personal access token with `read:packages` scope, kept on the
  host as `GHCR_TOKEN`.  Required because the repo images are private by
  default on ghcr.io.
- A bcrypt-hashed admin password for the basic-auth middleware:
  ```bash
  docker run --rm httpd:alpine htpasswd -nbB admin '<chosen-password>'
  # → admin:$2y$05$xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
  ```

---

## 1. First-time bootstrap (run **once** on the host)

```bash
ssh personal
sudo mkdir -p /opt/imamhadi/{compose,uploads,backups,secrets}
sudo chown -R ubuntu:ubuntu /opt/imamhadi
chmod 700 /opt/imamhadi/secrets

# Isolated docker network so we never touch n8n's `n8n_default`.
docker network create imamhadi_net

# Sanity: ports 80/443 must be free (n8n only owns 5678).
ss -tlnp | grep -E ':(80|443)\b' && echo "FATAL: 80/443 in use — investigate" || echo "ok"
```

From a developer laptop:

```bash
# Copy the compose dir + scripts from this repo to the server.
rsync -rv --exclude='.env' infra/ personal:/opt/imamhadi/compose/

# Then on the server, populate secrets + env.
ssh personal
cd /opt/imamhadi/compose
cp .env.example .env
$EDITOR .env                       # fill GH_OWNER/GH_REPO/PUBLIC_HOST/ACME_EMAIL/DB_PASSWORD/BASIC_AUTH_USERS/GHCR_TOKEN
echo -n '<DB_PASSWORD>' > /opt/imamhadi/secrets/db_password
chmod 600 /opt/imamhadi/secrets/db_password

# First deploy.
./scripts/deploy.sh
```

The first time Traefik starts it negotiates an ACME cert.  Tail logs
until you see `serverName=<your host>`, `Certificate obtained ...`:

```bash
docker compose -f docker-compose.prod.yml logs -f traefik | grep -iE 'acme|cert'
```

Then open `https://<PUBLIC_HOST>/`.  Browser asks for the basic-auth
credentials → admin sees the dashboard.

---

## 2. Day-to-day deploys

From a developer laptop:

```bash
# Cut a release (optional; you can also point IMAGE_TAG=latest on prod).
git tag v0.1.0 && git push --tags
# Wait for the `images` workflow to push to ghcr.io.

# Roll the host.
make deploy           # ssh personal + ./scripts/deploy.sh
make deploy.logs      # follow logs
make deploy.ps        # see container status
```

`scripts/deploy.sh` is idempotent:

1. Logs into ghcr.io if `GHCR_TOKEN` is set.
2. `docker compose pull` (no-op when images are already current).
3. `docker compose up -d --remove-orphans`.

n8n containers are on a different compose project (`n8n`) and a
different network (`n8n_default`); the `up -d` call here only touches
the `imamhadi` project.  Verify with `docker ps` post-deploy — every
`n8n_*` container's `StartedAt` should be unchanged.

---

## 3. Backups

Install a nightly `pg_dump` via the host's crontab (run **once**):

```bash
ssh personal
crontab -e
# add the following line — runs daily at 03:00 UTC, keeps 30 days.
0 3 * * * docker exec imamhadi-db-1 pg_dump -U imamhadi imamhadi | gzip > /opt/imamhadi/backups/imamhadi-$(date +\%Y\%m\%d).sql.gz && find /opt/imamhadi/backups -name 'imamhadi-*.sql.gz' -mtime +30 -delete
```

Ad-hoc backup from a developer laptop: `make deploy.backup`.

Restore:

```bash
ssh personal
gunzip < /opt/imamhadi/backups/imamhadi-YYYYMMDD.sql.gz \
  | docker exec -i imamhadi-db-1 psql -U imamhadi imamhadi
```

---

## 4. Rollback

Two strategies depending on the change:

- **Code regression** (bug in api/web): `IMAGE_TAG=v0.1.0-1 make deploy`
  on the prior good tag.  Alembic migrations apply on container start;
  if the new tag introduced a non-reversible migration, restore the DB
  from the most recent backup before rolling back.
- **Stack misconfig** (compose / Traefik): `git revert` the offending
  commit on `feat/p8-deploy` (or wherever), re-deploy, rsync the new
  `infra/` dir to `/opt/imamhadi/compose/`.

---

## 5. Co-tenancy guarantees with n8n

| Resource | imamhadi | n8n |
|---|---|---|
| Compose project name | `imamhadi` | `n8n` |
| Docker network | `imamhadi_net` (external) | `n8n_default` |
| Postgres volume | `imamhadi_pgdata` | `n8n_pgdata` |
| Public ports | `:80`, `:443`, `:443/udp` (Traefik) | `:5678` |
| Disk | `/opt/imamhadi/` only | `/home/ubuntu/n8n/` only |

The `images` GitHub Actions workflow builds `linux/amd64` only — same
arch as the VPS — so we never ship arm-only manifests by accident.

---

## 6. Operations cheat sheet

```bash
# Manual import via CLI on the host (faster than HTTP for big xlsm).
docker exec -i imamhadi-api-1 \
  python -m app.importer.cli /uploads/sample_data-14050208.xlsm

# Postgres console
ssh personal "docker exec -it imamhadi-db-1 psql -U imamhadi imamhadi"

# Rotate the basic-auth password
docker run --rm httpd:alpine htpasswd -nbB admin '<new>'
# → paste into .env BASIC_AUTH_USERS, then: make deploy
# (Traefik picks up label changes on container restart.)

# Rotate GHCR token
# → update .env GHCR_TOKEN, then: make deploy (script re-logs in).

# Wipe + restart fresh (DESTRUCTIVE — read first)
docker compose -f docker-compose.prod.yml down
docker volume rm imamhadi_pgdata          # nukes ALL data
./scripts/deploy.sh
```

---

## 7. Known gaps (Phase 2)

- n8n still listens on `:5678` without TLS.  Putting it behind the same
  Traefik (10-line Caddy-equivalent label addition on the n8n compose)
  is a Phase 1.5 follow-up.
- No Prometheus / Grafana / Sentry; relying on `docker logs` and access
  logs for now.  Add when load justifies.
- Single admin user; per-admin auth lands in Phase 2 alongside any
  write feature beyond the xlsm upload.
