"""Application factory.

Keeps all FastAPI wiring in one place — routers, middleware, CORS, OpenAPI
metadata. Import and call create_application() from main.py only.
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from habittracker.api import health
from habittracker.api.v1 import (
    bottle_events,
    dashboard,
    habit_logs,
    habits,
    notes,
    search,
)


def create_application() -> FastAPI:
    app = FastAPI(
        title="HabitTracker API",
        version="0.1.0",
        description="Manual logging MVP — habits, hydration, notes.",
    )

    # Allow the local Vite dev server to reach the API.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Health endpoints (no version prefix).
    app.include_router(health.router)

    # v1 feature routers.
    v1_prefix = "/api/v1"
    app.include_router(habits.router, prefix=v1_prefix)
    app.include_router(habit_logs.router, prefix=v1_prefix)
    app.include_router(bottle_events.router, prefix=v1_prefix)
    app.include_router(notes.router, prefix=v1_prefix)
    app.include_router(search.router, prefix=v1_prefix)
    app.include_router(dashboard.router, prefix=v1_prefix)

    return app
