# SliceIQ

Production-grade, AI-powered restaurant ordering platform.

[![CI](https://github.com/datawithdelio/sliceiq/actions/workflows/ci.yml/badge.svg)](https://github.com/datawithdelio/sliceiq/actions/workflows/ci.yml)
![Monorepo](https://img.shields.io/badge/Monorepo-Turborepo-0f172a)
![Frontend](https://img.shields.io/badge/Frontend-Next.js%2014-000000)
![Backend](https://img.shields.io/badge/Backend-FastAPI-059669)
![Database](https://img.shields.io/badge/Database-PostgreSQL%2015-336791)
![Cache](https://img.shields.io/badge/Cache-Redis%207-dc2626)

## Overview

SliceIQ is built as a scalable monorepo with:
- Customer storefront (`apps/customer`)
- Admin dashboard (`apps/admin`)
- FastAPI backend (`apps/backend`)
- ML workspace for models, pipelines, data simulation, and notebooks (`ml/*`)

## Architecture

```mermaid
flowchart LR
    C["Customer App (Next.js)"] --> API["FastAPI API"]
    A["Admin App (Next.js)"] --> API
    API --> DB["PostgreSQL"]
    API --> R["Redis"]
    M["ML Layer (models/pipelines/data/notebooks)"] -.-> API
```

## Monorepo Structure

```text
sliceiq/
├── apps/
│   ├── customer/     # Next.js 14 customer storefront
│   ├── admin/        # Next.js 14 admin dashboard
│   └── backend/      # FastAPI service
├── ml/
│   ├── models/
│   ├── pipelines/
│   ├── data/
│   └── notebooks/
├── .github/workflows/ci.yml
├── docker-compose.yml
├── .env.example
└── README.md
```

## Tech Stack

- Turborepo
- Next.js 14 + TypeScript + Tailwind CSS + App Router + ESLint
- FastAPI + Uvicorn
- PostgreSQL 15
- Redis 7
- Docker Compose
- GitHub Actions

## Quick Start

### 1. Configure Environment

```bash
cp .env.example .env
```

### 2. Run Backend Infrastructure

```bash
docker compose up --build
```

Services:
- API: `http://localhost:8000`
- Postgres: `localhost:5433` (mapped to container `5432`)
- Redis: `localhost:6379`

### 3. Run Frontends (separate terminals)

```bash
cd apps/customer && npm install && npm run dev
```

```bash
cd apps/admin && npm install && npm run dev
```

### 4. Health Check

```bash
curl http://localhost:8000/health
```

Expected response:

```json
{"status":"ok","service":"sliceiq-api"}
```

### 5. Upstash Redis (optional cloud Redis)

1. Copy your Upstash Redis URL (format: `rediss://default:<password>@<host>:<port>`).
2. Set it in `.env`:

```bash
UPSTASH_REDIS_URL=rediss://default:YOUR_PASSWORD@YOUR_HOST:YOUR_PORT
```

3. Rebuild and restart API:

```bash
docker compose up -d --build api
```

4. Verify Redis connectivity:

```bash
curl http://localhost:8000/ping-redis
```

## CI Pipeline

GitHub Actions runs on pushes and pull requests to `main`:
- Backend: Python 3.11 + `pytest`
- Frontends: install + build for `customer` and `admin`

## Created By

Delio Rincon & Renzo Montoya
