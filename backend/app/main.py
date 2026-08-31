"""FastAPI application entry point."""
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi.errors import RateLimitExceeded

from app.core.config import settings
from app.core.rate_limit import limiter
from app.auth.router import router as auth_router
from app.users.router import router as users_router
from app.groups.router import router as groups_router
from app.categories.router import router as categories_router
from app.payment_methods.router import router as payment_methods_router
from app.obligations.router import router as obligations_router
from app.obligations.router import periods_router
from app.payments.router import router as payments_router
from app.payments.router import period_payments_router
from app.dashboard.router import router as dashboard_router

app = FastAPI(title="Family Project API", version="0.1.0")
app.state.limiter = limiter

# ---------------------------------------------------------------------------
# CORS — allow-list exacta del frontend (ADR-008)
# ---------------------------------------------------------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.FRONTEND_ORIGIN],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Rate limiting middleware (ADR-008)
# ---------------------------------------------------------------------------
from slowapi.middleware import SlowAPIMiddleware
app.add_middleware(SlowAPIMiddleware)

# ---------------------------------------------------------------------------
# Routers
# ---------------------------------------------------------------------------
app.include_router(auth_router, prefix="/api/v1")
app.include_router(users_router, prefix="/api/v1")
app.include_router(groups_router, prefix="/api/v1")
app.include_router(categories_router, prefix="/api/v1")
app.include_router(payment_methods_router, prefix="/api/v1")
app.include_router(obligations_router, prefix="/api/v1")
app.include_router(periods_router, prefix="/api/v1")
app.include_router(payments_router, prefix="/api/v1")
app.include_router(period_payments_router, prefix="/api/v1")
app.include_router(dashboard_router, prefix="/api/v1")


# ---------------------------------------------------------------------------
# Exception handler — flatten HTTPException detail when it carries our
# {"detail": "...", "code": "..."} format, so the response JSON is
# {"detail": "...", "code": "..."} at the top level (not nested).
# ---------------------------------------------------------------------------
@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    if isinstance(exc.detail, dict) and "detail" in exc.detail and "code" in exc.detail:
        return JSONResponse(status_code=exc.status_code, content=exc.detail)
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})


@app.exception_handler(RateLimitExceeded)
async def rate_limit_exception_handler(request: Request, exc: RateLimitExceeded):
    return JSONResponse(
        status_code=429,
        content={"detail": "Demasiadas solicitudes. Intenta de nuevo más tarde.", "code": "RATE_LIMIT_EXCEEDED"},
    )


@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception):
    return JSONResponse(status_code=500, content={"detail": "Internal server error", "code": "INTERNAL_ERROR"})
