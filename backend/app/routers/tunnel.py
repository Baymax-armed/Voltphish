"""Public-URL (Cloudflare Tunnel) status for the campaign form."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from ..dependencies import get_current_user
from ..services.tunnel import detect_public_url, is_configured

router = APIRouter(
    prefix="/api/v1/tunnel",
    tags=["tunnel"],
    dependencies=[Depends(get_current_user)],
)


class TunnelOut(BaseModel):
    configured: bool  # a cloudflared sidecar is wired up
    url: str | None    # its current public URL, if the tunnel is up


@router.get("", response_model=TunnelOut)
def tunnel_status() -> TunnelOut:
    return TunnelOut(configured=is_configured(), url=detect_public_url())
