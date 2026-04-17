from fastapi import APIRouter, Depends, HTTPException

from app.deps import require_viewer
from app.models.server import Server
from app.models.user import AppUser

router = APIRouter(prefix="/api", tags=["api"])


@router.get("/servers")
async def api_list_servers(user: AppUser = Depends(require_viewer)) -> list[dict]:
    return [s.summary() for s in Server.objects.order_by("hostname")]


@router.get("/servers/{server_id}")
async def api_get_server(
    server_id: str,
    user: AppUser = Depends(require_viewer),
) -> dict:
    server = Server.get(server_id)
    if not server:
        raise HTTPException(status_code=404, detail="Server not found")
    return server.to_dict()
