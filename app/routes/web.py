from fastapi import APIRouter, Depends, Form, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from app.deps import require_admin, require_editor, require_viewer, templates
from app.models.server import ENVIRONMENTS, SERVER_TYPES, STATUSES, Server
from app.models.user import AppUser
from app.services.markdown import render_markdown

router = APIRouter(tags=["web"])


FORM_FIELDS = {
    "server_types": SERVER_TYPES,
    "environments": ENVIRONMENTS,
    "statuses": STATUSES,
}


@router.get("/", response_class=HTMLResponse)
async def index(request: Request, user: AppUser = Depends(require_viewer)):
    recent = Server.objects.order_by("-last_updated")[:10]
    return templates.TemplateResponse(
        request,
        "index.html",
        {"user": user, "recent": list(recent)},
    )


@router.get("/servers", response_class=HTMLResponse)
async def list_servers(
    request: Request,
    q: str | None = Query(default=None),
    environment: str | None = Query(default=None),
    status: str | None = Query(default=None),
    user: AppUser = Depends(require_viewer),
):
    filters: dict = {}
    if q:
        filters["hostname"] = q
    if environment:
        filters["environment"] = environment
    if status:
        filters["status"] = status

    servers = Server.search(_order_by=["hostname"], **filters) if filters else Server.search(_order_by=["hostname"])
    return templates.TemplateResponse(
        request,
        "servers/list.html",
        {
            "user": user,
            "servers": servers,
            "filters": {"q": q or "", "environment": environment or "", "status": status or ""},
            **FORM_FIELDS,
        },
    )


@router.get("/servers/search", response_class=HTMLResponse)
async def search_servers(
    request: Request,
    q: str = Query(default=""),
    user: AppUser = Depends(require_viewer),
):
    q = q.strip()
    if not q:
        servers = []
    else:
        servers = Server.search(_order_by=["hostname"], _limit=25, hostname=q)
    return templates.TemplateResponse(
        request,
        "partials/search_results.html",
        {"servers": servers, "q": q},
    )


@router.get("/servers/new", response_class=HTMLResponse)
async def new_server_form(request: Request, user: AppUser = Depends(require_editor)):
    return templates.TemplateResponse(
        request,
        "servers/form.html",
        {"user": user, "server": None, **FORM_FIELDS},
    )


@router.post("/servers")
async def create_server(
    request: Request,
    user: AppUser = Depends(require_editor),
):
    form = await request.form()
    server = Server(hostname=_clean(form.get("hostname")))
    if not server.hostname:
        raise HTTPException(status_code=400, detail="hostname is required")
    _apply_form(server, form)
    server.save()
    return RedirectResponse(url=f"/servers/{server.pk}", status_code=303)


@router.get("/servers/{server_id}", response_class=HTMLResponse)
async def server_detail(
    request: Request,
    server_id: str,
    user: AppUser = Depends(require_viewer),
):
    server = Server.get(server_id)
    if not server:
        raise HTTPException(status_code=404)
    return templates.TemplateResponse(
        request,
        "servers/detail.html",
        {"user": user, "server": server},
    )


@router.get("/servers/{server_id}/edit", response_class=HTMLResponse)
async def edit_server_form(
    request: Request,
    server_id: str,
    user: AppUser = Depends(require_editor),
):
    server = Server.get(server_id)
    if not server:
        raise HTTPException(status_code=404)
    return templates.TemplateResponse(
        request,
        "servers/form.html",
        {"user": user, "server": server, **FORM_FIELDS},
    )


@router.post("/servers/{server_id}")
async def update_server(
    request: Request,
    server_id: str,
    user: AppUser = Depends(require_editor),
):
    server = Server.get(server_id)
    if not server:
        raise HTTPException(status_code=404)
    form = await request.form()
    hostname = _clean(form.get("hostname"))
    if hostname:
        server.hostname = hostname
    _apply_form(server, form)
    server.save()
    return RedirectResponse(url=f"/servers/{server.pk}", status_code=303)


@router.post("/servers/{server_id}/delete")
async def delete_server(
    server_id: str,
    user: AppUser = Depends(require_admin),
):
    server = Server.get(server_id)
    if not server:
        raise HTTPException(status_code=404)
    server.delete()
    return RedirectResponse(url="/servers", status_code=303)


@router.post("/servers/preview-notes", response_class=HTMLResponse)
async def preview_notes(
    request: Request,
    user: AppUser = Depends(require_editor),
):
    form = await request.form()
    raw = form.get("notes") or ""
    return HTMLResponse(render_markdown(raw))


def _apply_form(server: Server, form) -> None:
    string_fields = [
        "fqdn", "server_type", "hypervisor", "os_name", "os_version", "kernel",
        "cpu_model", "vendor", "product_name", "serial_number", "asset_tag",
        "rack", "location", "vlan", "environment", "purpose", "owner", "status",
        "patch_window", "notes",
    ]
    for name in string_fields:
        if name in form:
            setattr(server, name, _clean(form.get(name)))

    for name in ("cpu_cores", "ram_bytes", "disk_bytes"):
        raw = (form.get(name) or "").strip()
        if raw:
            try:
                setattr(server, name, int(raw))
            except ValueError:
                pass

    for name in ("ip_addresses", "mac_addresses", "tags", "compliance_tags"):
        if name in form:
            raw = form.get(name) or ""
            values = [v.strip() for v in raw.replace("\n", ",").split(",") if v.strip()]
            setattr(server, name, values)


def _clean(value) -> str:
    return (value or "").strip() if isinstance(value, str) else ""
