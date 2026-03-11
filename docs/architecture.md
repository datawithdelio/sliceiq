# SliceIQ Architecture (v1)

```mermaid
flowchart LR
  subgraph Clients
    CustomerApp[Customer App]
    AdminApp[Admin App]
  end

  subgraph Backend
    API[FastAPI Backend]
    Redis[(Redis / Upstash)]
    Postgres[(PostgreSQL / Neon)]
  end

  subgraph External
    Stripe[Stripe Checkout]
    StripeWebhook[Stripe Webhook (not implemented)]
  end

  subgraph ML
    MLArtifacts[ML Artifacts & Reports\nml/models + ml/data/reports]
  end

  CustomerApp -->|HTTP| API
  AdminApp -->|HTTP| API

  API --> Postgres
  API --> Redis
  API --> Stripe
  Stripe --> StripeWebhook

  MLArtifacts -->|Churn model + monitoring inputs| API
```

Notes:
- Backend routes and services reflect `apps/backend/app/main.py` and routers under `apps/backend/app/api`.
- Redis integration is via `/ping-redis` and `app/core/redis.py`.
- Stripe webhook handling is not implemented in the repo; shown for integration completeness.
