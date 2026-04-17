from authlib.integrations.starlette_client import OAuth, OAuthError
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import RedirectResponse

from app.config import get_settings
from app.models.user import AppUser

router = APIRouter(prefix="/auth", tags=["auth"])

_oauth = OAuth()
_settings = get_settings()

_oauth.register(
    name="google",
    client_id=_settings.google_client_id,
    client_secret=_settings.google_client_secret,
    server_metadata_url=_settings.google_discovery_url,
    client_kwargs={"scope": "openid email profile"},
)


@router.get("/login")
async def login(request: Request):
    redirect_uri = _settings.google_redirect_url or str(request.url_for("auth_callback"))
    return await _oauth.google.authorize_redirect(request, redirect_uri)


@router.get("/callback", name="auth_callback")
async def callback(request: Request):
    try:
        token = await _oauth.google.authorize_access_token(request)
    except OAuthError as exc:
        raise HTTPException(status_code=400, detail=f"OAuth failure: {exc.error}")

    userinfo = token.get("userinfo") or await _oauth.google.userinfo(token=token)
    email = (userinfo.get("email") or "").strip().lower()
    if not email:
        raise HTTPException(status_code=400, detail="Google did not return an email")

    if _settings.allowed_email_domains:
        domain = email.split("@", 1)[-1]
        if domain not in _settings.allowed_email_domains:
            raise HTTPException(
                status_code=403,
                detail=f"Login restricted to: {', '.join(_settings.allowed_email_domains)}",
            )

    user = AppUser.authenticate(userinfo, token=token.get("id_token"))
    request.session["user_pk"] = str(user.pk)
    return RedirectResponse(url="/", status_code=303)


@router.get("/logout")
async def logout(request: Request):
    request.session.clear()
    return RedirectResponse(url="/", status_code=303)
