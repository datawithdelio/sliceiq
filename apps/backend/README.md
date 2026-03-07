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
