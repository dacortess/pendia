"""Auth endpoints — register, login, refresh, logout."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Response, Request
from sqlalchemy.orm import Session

from app.database.session import get_db_session
from app.core.config import settings
from app.auth.schemas import RegisterRequest, LoginRequest, AccessTokenResponse
from app.auth import service
from app.core.rate_limit import limiter

router = APIRouter(prefix="/auth", tags=["auth"])

COOKIE_MAX_AGE = settings.REFRESH_TOKEN_TTL_DAYS * 24 * 60 * 60  # seconds


# ---------------------------------------------------------------------------
# POST /register
# ---------------------------------------------------------------------------

@router.post("/register", response_model=AccessTokenResponse, status_code=201)
@limiter.limit("10/minute")
def register(request: Request, body: RegisterRequest, response: Response, db: Session = Depends(get_db_session)):
    try:
        access_token, refresh_token = service.register(
            db,
            email=body.email,
            password=body.password,
            full_name=body.full_name,
            phone_number=body.phone_number,
            invite_code=body.invite_code,
        )
    except service.AuthError as exc:
        from fastapi import HTTPException
        raise HTTPException(status_code=exc.status_code, detail={"detail": exc.detail, "code": exc.code})

    response.set_cookie(
        "refresh_token",
        refresh_token,
        httponly=True,
        secure=True,
        samesite="none",
        path="/api/v1/auth/refresh",
        max_age=COOKIE_MAX_AGE,
    )
    return AccessTokenResponse(access_token=access_token)


# ---------------------------------------------------------------------------
# POST /login
# ---------------------------------------------------------------------------

@router.post("/login", response_model=AccessTokenResponse)
@limiter.limit("10/minute")
def login(request: Request, body: LoginRequest, response: Response, db: Session = Depends(get_db_session)):
    try:
        access_token, refresh_token = service.authenticate(
            db,
            email=body.email,
            password=body.password,
        )
    except service.AuthError as exc:
        from fastapi import HTTPException
        raise HTTPException(status_code=exc.status_code, detail={"detail": exc.detail, "code": exc.code})

    response.set_cookie(
        "refresh_token",
        refresh_token,
        httponly=True,
        secure=True,
        samesite="none",
        path="/api/v1/auth/refresh",
        max_age=COOKIE_MAX_AGE,
    )
    return AccessTokenResponse(access_token=access_token)


# ---------------------------------------------------------------------------
# POST /refresh
# ---------------------------------------------------------------------------

@router.post("/refresh", response_model=AccessTokenResponse)
@limiter.limit("10/minute")
def refresh_token(request: Request, response: Response, db: Session = Depends(get_db_session)):
    cookie_value = request.cookies.get("refresh_token", "")
    try:
        access_token, new_refresh_token = service.refresh(db, refresh_token_value=cookie_value)
    except service.AuthError as exc:
        from fastapi import HTTPException
        raise HTTPException(status_code=exc.status_code, detail={"detail": exc.detail, "code": exc.code})

    response.set_cookie(
        "refresh_token",
        new_refresh_token,
        httponly=True,
        secure=True,
        samesite="none",
        path="/api/v1/auth/refresh",
        max_age=COOKIE_MAX_AGE,
    )
    return AccessTokenResponse(access_token=access_token)


# ---------------------------------------------------------------------------
# POST /logout
# ---------------------------------------------------------------------------

@router.post("/logout", status_code=204)
def logout(request: Request, response: Response, db: Session = Depends(get_db_session)):
    cookie_value = request.cookies.get("refresh_token", "")
    service.logout(db, refresh_token_value=cookie_value)
    response.delete_cookie("refresh_token", path="/api/v1/auth/refresh")
    return Response(status_code=204)
