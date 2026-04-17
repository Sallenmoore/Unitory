from pathlib import Path

from fastapi import Depends, HTTPException, Request
from fastapi.templating import Jinja2Templates

from app.models.user import AppUser
from app.services.markdown import render_markdown

_TEMPLATES_DIR = Path(__file__).resolve().parent / "templates"
templates = Jinja2Templates(directory=str(_TEMPLATES_DIR))
templates.env.filters["markdown"] = render_markdown


def get_current_user(request: Request) -> AppUser | None:
    pk = request.session.get("user_pk")
    if not pk:
        return None
    return AppUser.get(pk)


def _attach_user(request: Request, user: AppUser | None) -> None:
    # Makes `user` available in templates via request.state.user.
    request.state.user = user


def require_viewer(request: Request) -> AppUser:
    user = get_current_user(request)
    if not user or not user.is_authenticated:
        raise HTTPException(status_code=401)
    _attach_user(request, user)
    return user


def require_editor(user: AppUser = Depends(require_viewer)) -> AppUser:
    if not user.is_editor:
        raise HTTPException(status_code=403)
    return user


def require_admin(user: AppUser = Depends(require_viewer)) -> AppUser:
    if not user.is_admin:
        raise HTTPException(status_code=403)
    return user


def optional_user(request: Request) -> AppUser | None:
    user = get_current_user(request)
    _attach_user(request, user)
    return user
