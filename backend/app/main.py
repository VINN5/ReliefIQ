from contextlib import asynccontextmanager
import logging

from fastapi import Depends, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api.v1.auth import limiter, router as auth_router
from app.api.v1.documents import router as documents_router
from app.api.v1.query import router as query_router
from app.config import settings
from app.database import get_db
from app.services.embedding_service import warm_up as warm_up_embedding_model
from app.api.v1 import gap_detection
from app.api.v1 import conversations
from app.api.v1 import admin_audit_log
from app.api.v1 import conflict_detection
from app.api.v1 import spreadsheets

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Load the embedding model now, at startup, instead of on whichever
    # request happens to be first. Without this, the first upload or
    # query after every server restart eats a multi-second model-load
    # penalty that looks like random slowness rather than a one-time cost.
    warm_up_embedding_model()
    yield


app = FastAPI(title="ReliefIQ API", version="0.1.0", lifespan=lifespan)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Allows the Vite dev server (localhost:5173) to call this API from the browser.
# Add your real deployed frontend origin here too once you have one.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(documents_router)
app.include_router(query_router)
app.include_router(gap_detection.router)
app.include_router(conversations.router)
app.include_router(admin_audit_log.router)
app.include_router(conflict_detection.router)
app.include_router(spreadsheets.router)

@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    """
    Without this, an unhandled exception produces a 500 response that
    never gets CORS headers attached — the browser blocks it entirely,
    and the frontend sees a generic "network failure" instead of the
    real error. This makes every backend bug look like "server is down."
    """
    logger.exception("Unhandled exception on %s %s", request.method, request.url.path)
    return JSONResponse(
        status_code=500,
        content={"detail": "Something went wrong processing your request."},
    )


@app.get("/health")
def health_check():
    """Confirms the API process itself is up."""
    return {"status": "ok", "env": settings.app_env}


@app.get("/health/db")
def health_check_db(db: Session = Depends(get_db)):
    """Confirms the API can actually reach and query Postgres."""
    db.execute(text("SELECT 1"))
    return {"status": "ok", "database": "connected"}