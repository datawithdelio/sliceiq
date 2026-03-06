# SliceIQ

AI-powered restaurant ordering platform.

## Tech Stack

- Turborepo monorepo
- Next.js 14 (TypeScript, Tailwind CSS, App Router, ESLint)
- FastAPI (Python)
- PostgreSQL
- Redis
- Docker Compose
- GitHub Actions

## Run Locally

1. Copy environment variables:
   ```bash
   cp .env.example .env
   ```
2. Start backend stack:
   ```bash
   docker-compose up --build
   ```
3. Run frontend apps in separate terminals:
   ```bash
   cd apps/customer && npm install && npm run dev
   ```
   ```bash
   cd apps/admin && npm install && npm run dev
   ```

## Created By

Delio Rincon & Renzo Montoya
