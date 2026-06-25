from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.health import router as health_router
from app.api.qr_login import router as qr_login_router
from app.api.ws import router as ws_router
from app.api.competition import router as competition_router
from app.api.monitor import router as monitor_router
from app.api.replay import router as replay_router
from app.core.database import init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Ensure all database tables exist on application startup."""
    init_db()
    yield


app = FastAPI(title="Weibo Hot-Comment Monitor", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health_router)
app.include_router(qr_login_router)
app.include_router(ws_router)
app.include_router(competition_router)
app.include_router(monitor_router)
app.include_router(replay_router)
