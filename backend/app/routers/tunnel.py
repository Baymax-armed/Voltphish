"""Public-URL (Cloudflare Tunnel) status for the campaign form."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from ..dependencies import get_current_user
from ..services.tunnel import detect_public_url, is_configured, managed_available

router = APIRouter(
    prefix="/api/v1/tunnel",
    tags=["tunnel"],
    dependencies=[Depends(get_current_user)],
)


class TunnelOut(BaseModel):
    configured: bool   # a shared cloudflared sidecar is wired up
    url: str | None    # the shared sidecar's current public URL, if up
    managed: bool      # the app can spawn a fresh per-campaign tunnel itself


@router.get("", response_model=TunnelOut)
def tunnel_status() -> TunnelOut:
    return TunnelOut(configured=is_configured(), url=detect_public_url(), managed=managed_available())
