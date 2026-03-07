# SliceIQ Backend

## Database Setup

The canonical schema lives at `migrations/schema.sql`.

### Configure environment

Set `DATABASE_URL` in your environment (see `.env.example` at the repo root). For Neon, use the connection string from your Neon project with `sslmode=require`.

Example:

```bash
export DATABASE_URL="postgresql://USER:PASSWORD@HOST/DBNAME?sslmode=require"
```

### Run migrations (apply schema)

Run the schema against your database using `psql`:

```bash
psql "$DATABASE_URL" -f migrations/schema.sql
```

## Connect to Neon

1. Create or select a Neon project and database.
2. Copy the connection string from the Neon dashboard.
3. Set `DATABASE_URL` to that connection string (ensure `sslmode=require`).
4. Use the `psql` command above to apply `migrations/schema.sql`.

## Connect to Upstash Redis

1. Copy your Upstash Redis URL from the Upstash dashboard.
2. Set `UPSTASH_REDIS_URL` in your `.env` (repo root).

Example:

```bash
UPSTASH_REDIS_URL="rediss://default:YOUR_PASSWORD@YOUR_HOST:YOUR_PORT"
```

3. Restart the API container so env changes are applied:

```bash
docker compose up -d --build api
```

4. Verify Redis integration:

```bash
curl http://localhost:8000/ping-redis
```

## Alembic Migrations

Alembic is configured in:
- `alembic.ini`
- `alembic/env.py`
- `alembic/versions/*`

Baseline revision:
- `20260306_0001`

Run Alembic from the backend container (recommended):

```bash
docker compose run --rm api alembic -c alembic.ini upgrade head
```

Create a new migration:

```bash
docker compose run --rm api alembic -c alembic.ini revision -m "describe change"
```

## Clerk JWT Protection

Protected routes are mounted under:
- `/protected/*`

Current test endpoint:
- `GET /protected/me`

Required env vars for JWT verification:
- `CLERK_ISSUER` (recommended) or `CLERK_JWKS_URL`
- `CLERK_AUDIENCE` (optional)

If you set `CLERK_ISSUER`, JWKS defaults to:
- `{CLERK_ISSUER}/.well-known/jwks.json`

## Synthetic Data Simulator (Day 5 ML)

Script path:
- `scripts/seed_data.py`

What it generates:
- 200 synthetic users (`@synthetic.sliceiq.local`)
- 6-month order history with:
  - lunch/dinner rush-hour weighting (12-2pm, 6-9pm)
  - weekday-heavy behavior
  - ~30% power/repeat users
- 1-5 order items per order from existing products

Idempotency:
- Synthetic users are created only up to 200.
- Existing synthetic users' orders/order_items are replaced on each run (no duplicates).

Run locally:

```bash
cd apps/backend
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python scripts/seed_data.py
```

The script prints:
- `Seeded X users, Y orders, Z order_items`
- `Behavior Report: rush_hour_pct=..., weekday_pct=..., weekend_pct=..., repeat_user_pct=..., power_user_pct=...`
