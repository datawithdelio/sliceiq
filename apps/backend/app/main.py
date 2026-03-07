import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

import app.models  # noqa: F401
from app.api.protected import router as protected_router
from app.api.health import router as health_router
from app.api.redis_ping import router as redis_ping_router
from app.routers.products import router as products_router

app = FastAPI(title="SliceIQ API")

frontend_origins = os.getenv("FRONTEND_ORIGINS", "http://localhost:3000")
allowed_origins = [origin.strip() for origin in frontend_origins.split(",") if origin.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health_router)
app.include_router(redis_ping_router)
app.include_router(protected_router)
app.include_router(products_router)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
