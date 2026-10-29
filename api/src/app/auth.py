"""Who is making this request.

Traefik's basic-auth middleware verifies the password and forwards the
``Authorization`` header unchanged; the API only decodes the username
(it is never published outside Traefik, so the header cannot be forged
from outside).  Without the header — local development — the configured
``dev_user`` is used.  Every user is an admin for now.
"""

from __future__ import annotations

import base64
import binascii
from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

from app.config import settings
from app.db import SessionDep
from app.models import AppUser

_MAX_USERNAME = 64  # app_user.username width


def username_from(request: Request) -> str:
    header = request.headers.get("authorization", "")
    scheme, _, token = header.partition(" ")
    if scheme.lower() == "basic" and token:
        try:
            user, _, _ = base64.b64decode(token).decode("utf-8").partition(":")
        except (binascii.Error, UnicodeDecodeError):
            user = ""
        # Printable, no control characters, within the column width — else ignore.
        if user and user.isprintable() and len(user) <= _MAX_USERNAME:
            return user
    return settings.dev_user


async def current_user(request: Request, session: SessionDep) -> AppUser:
    """The acting user, created on first sight."""
    name = username_from(request)
    await session.execute(
        insert(AppUser).values(username=name).on_conflict_do_nothing(index_elements=["username"])
    )
    return (await session.execute(select(AppUser).where(AppUser.username == name))).scalar_one()


CurrentUser = Annotated[AppUser, Depends(current_user)]
