from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

from app.config import get_settings
from app.deps import templates
from app.routes import admin, api, auth, web

BASE_DIR = Path(__file__).resolve().parent


def create_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(title="Unitory", docs_url=None, redoc_url=None)

    app.add_middleware(
        SessionMiddleware,
        secret_key=settings.session_secret,
        same_site="lax",
        https_only=settings.app_base_url.startswith("https://"),
    )

    app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")

    app.include_router(auth.router)
    app.include_router(api.router)
    app.include_router(admin.router)
    app.include_router(web.router)

    @app.exception_handler(401)
    async def _unauthorized(request: Request, exc):
        # API paths get JSON, HTML paths get redirected to login.
        if request.url.path.startswith("/api/"):
            return HTMLResponse("Unauthorized", status_code=401)
        return RedirectResponse(url="/auth/login", status_code=303)

    @app.exception_handler(403)
    async def _forbidden(request: Request, exc):
        if request.url.path.startswith("/api/"):
            return HTMLResponse("Forbidden", status_code=403)
        return templates.TemplateResponse(
            request, "403.html", {"message": "You don't have access to that page."}, status_code=403
        )

    return app


app = create_app()
