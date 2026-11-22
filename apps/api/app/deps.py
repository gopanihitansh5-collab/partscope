from __future__ import annotations

from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.orm import Session

from src.common.db import get_session

SessionDep = Annotated[Session, Depends(get_session)]


def request_id(request: Request) -> str | None:
    return getattr(request.state, "request_id", None)


RequestIdDep = Annotated[str | None, Depends(request_id)]
