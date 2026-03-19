from datetime import UTC, datetime
from urllib.parse import urlencode

from fastapi import APIRouter, Cookie, Depends, HTTPException, Query, Response, status
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.config import get_settings
from src.core.dependencies import get_current_user
from src.core.security import TokenError, create_oauth_state, decode_token
from src.infrastructure.auth.google_oauth_client import GoogleOAuthClient
from src.infrastructure.database.session import get_db_session
from src.modules.auth.schemas import AuthUserResponse
from src.modules.auth.service import AuthService

settings = get_settings()
router = APIRouter(prefix="/auth", tags=["auth"])


def _set_auth_cookies(response: Response, access_token: str, refresh_token: str) -> None:
    response.set_cookie(
        key=settings.access_cookie_name,
        value=access_token,
        httponly=True,
        secure=settings.cookie_secure,
        samesite=settings.cookie_samesite,
        domain=settings.cookie_domain,
        max_age=settings.access_token_expire_minutes * 60,
        path="/",
    )
    response.set_cookie(
        key=settings.refresh_cookie_name,
        value=refresh_token,
        httponly=True,
        secure=settings.cookie_secure,
        samesite=settings.cookie_samesite,
        domain=settings.cookie_domain,
        max_age=settings.refresh_token_expire_days * 24 * 60 * 60,
        path="/",
    )


def _clear_auth_cookies(response: Response) -> None:
    response.delete_cookie(settings.access_cookie_name, domain=settings.cookie_domain, path="/")
    response.delete_cookie(settings.refresh_cookie_name, domain=settings.cookie_domain, path="/")
    response.delete_cookie(settings.oauth_state_cookie_name, domain=settings.cookie_domain, path="/")


@router.get("/google/login")
async def google_login() -> Response:
    state = create_oauth_state()
    client = GoogleOAuthClient()
    login_url = client.build_login_url(state)

    response = RedirectResponse(url=login_url, status_code=status.HTTP_307_TEMPORARY_REDIRECT)
    response.set_cookie(
        key=settings.oauth_state_cookie_name,
        value=state,
        httponly=True,
        secure=settings.cookie_secure,
        samesite=settings.cookie_samesite,
        domain=settings.cookie_domain,
        max_age=10 * 60,
        path="/",
    )
    return response


@router.get("/google/callback")
async def google_callback(
    code: str | None = Query(default=None),
    state: str | None = Query(default=None),
    oauth_state_cookie: str | None = Cookie(default=None, alias=settings.oauth_state_cookie_name),
    session: AsyncSession = Depends(get_db_session),
) -> Response:
    if not code:
        query = urlencode({"message": "missing_google_code"})
        return RedirectResponse(f"{settings.frontend_login_failure_redirect}?{query}")

    if not state or not oauth_state_cookie or state != oauth_state_cookie:
        query = urlencode({"message": "invalid_oauth_state"})
        return RedirectResponse(f"{settings.frontend_login_failure_redirect}?{query}")

    client = GoogleOAuthClient()
    try:
        token_response = await client.exchange_code(code)
        profile = await client.get_profile(token_response)
    except HTTPException:
        query = urlencode({"message": "google_auth_failed"})
        return RedirectResponse(f"{settings.frontend_login_failure_redirect}?{query}")

    service = AuthService(session)
    _, tokens = await service.login_with_google(profile)

    redirect_response = RedirectResponse(
        url=settings.frontend_login_success_redirect,
        status_code=status.HTTP_307_TEMPORARY_REDIRECT,
    )
    _set_auth_cookies(redirect_response, tokens.access_token, tokens.refresh_token)
    redirect_response.delete_cookie(settings.oauth_state_cookie_name, domain=settings.cookie_domain, path="/")
    return redirect_response


@router.post("/refresh")
async def refresh_token(
    response: Response,
    refresh_token_cookie: str | None = Cookie(default=None, alias=settings.refresh_cookie_name),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    if not refresh_token_cookie:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing refresh token")

    service = AuthService(session)
    user_id, tokens = await service.refresh(refresh_token_cookie)
    _set_auth_cookies(response, tokens.access_token, tokens.refresh_token)

    return {
        "user_id": str(user_id),
        "refreshed_at": datetime.now(UTC).isoformat(),
    }


@router.post("/logout")
async def logout(
    response: Response,
    access_token_cookie: str | None = Cookie(default=None, alias=settings.access_cookie_name),
    refresh_token_cookie: str | None = Cookie(default=None, alias=settings.refresh_cookie_name),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    resolved_user_id = None
    if access_token_cookie:
        try:
            from uuid import UUID

            payload = decode_token(access_token_cookie, expected_type="access")
            resolved_user_id = UUID(payload["sub"])
        except (TokenError, ValueError, KeyError):
            resolved_user_id = None

    service = AuthService(session)
    await service.logout(resolved_user_id, refresh_token_cookie)
    _clear_auth_cookies(response)

    return {"message": "Logged out"}


@router.get("/me", response_model=AuthUserResponse)
async def me(current_user=Depends(get_current_user)) -> AuthUserResponse:
    return AuthUserResponse(
        id=current_user.id,
        email=current_user.email,
        full_name=current_user.full_name,
        avatar_url=current_user.avatar_url,
    )
