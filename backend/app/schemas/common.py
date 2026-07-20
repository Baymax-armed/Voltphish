from __future__ import annotations

from pydantic import BaseModel


class Message(BaseModel):
    detail: str
