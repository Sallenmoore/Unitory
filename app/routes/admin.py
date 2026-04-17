from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from app.deps import require_admin, templates
from app.models.discovery_job import DiscoveryJob
from app.models.user import ROLES, AppUser
from app.services.discovery import enqueue_scan

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("", response_class=HTMLResponse)
async def admin_index(request: Request, user: AppUser = Depends(require_admin)):
    return templates.TemplateResponse(request, "admin/index.html", {"user": user})


@router.get("/users", response_class=HTMLResponse)
async def admin_users(request: Request, user: AppUser = Depends(require_admin)):
    users = list(AppUser.objects.order_by("email"))
    return templates.TemplateResponse(
        request,
        "admin/users.html",
        {"user": user, "users": users, "roles": ROLES},
    )


@router.post("/users/{user_id}/role")
async def admin_set_role(
    user_id: str,
    role: str = Form(...),
    user: AppUser = Depends(require_admin),
):
    if role not in ROLES:
        raise HTTPException(status_code=400, detail="Invalid role")
    target = AppUser.get(user_id)
    if not target:
        raise HTTPException(status_code=404)
    if str(target.pk) == str(user.pk) and role != "admin":
        raise HTTPException(status_code=400, detail="You cannot remove your own admin access")
    target.role = role
    target.save()
    return RedirectResponse(url="/admin/users", status_code=303)


@router.post("/users/{user_id}/delete")
async def admin_delete_user(
    user_id: str,
    user: AppUser = Depends(require_admin),
):
    target = AppUser.get(user_id)
    if not target:
        raise HTTPException(status_code=404)
    if str(target.pk) == str(user.pk):
        raise HTTPException(status_code=400, detail="You cannot delete yourself")
    target.delete()
    return RedirectResponse(url="/admin/users", status_code=303)


@router.get("/discovery", response_class=HTMLResponse)
async def admin_discovery(request: Request, user: AppUser = Depends(require_admin)):
    jobs = list(DiscoveryJob.objects.order_by("-last_updated")[:20])
    return templates.TemplateResponse(
        request,
        "admin/discovery.html",
        {"user": user, "jobs": jobs, "default_port": 9100},
    )


@router.post("/discovery/scan")
async def admin_discovery_scan(
    request: Request,
    hostnames: str = Form(...),
    port: int = Form(9100),
    user: AppUser = Depends(require_admin),
):
    host_list = [line.strip() for line in hostnames.splitlines() if line.strip()]
    if not host_list:
        raise HTTPException(status_code=400, detail="Provide at least one hostname")
    job = enqueue_scan(host_list, port=port, requested_by=user.email)
    return RedirectResponse(url=f"/admin/discovery#job-{job.pk}", status_code=303)


@router.get("/discovery/jobs/{job_id}", response_class=HTMLResponse)
async def admin_discovery_job(
    request: Request,
    job_id: str,
    user: AppUser = Depends(require_admin),
):
    job = DiscoveryJob.get(job_id)
    if not job:
        raise HTTPException(status_code=404)
    return templates.TemplateResponse(
        request,
        "admin/_job_status.html",
        {"job": job},
    )
