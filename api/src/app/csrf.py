"""Cross-site request guard for every state-changing request.

The dashboard sits behind HTTP basic-auth, which browsers attach to any
request — including a form another site submits.  A plain multipart POST
needs no CORS preflight, so CORS alone does not stop it.  Browsers always
send ``Origin`` (or at least ``Referer``) on such requests: refuse unsafe
methods whose origin is neither this host nor an allowed CORS origin.
Requests with neither header (curl, the CLI, tests) are not browser-driven
and pass.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from urllib.parse import urlsplit

from fastapi import Request, Response
from fastapi.responses import JSONResponse

from app.config import settings

_SAFE = {"GET", "HEAD", "OPTIONS"}


def _netloc(url: str) -> str:
    return urlsplit(url).netloc.lower()


async def same_origin_only(
    request: Request, call_next: Callable[[Request], Awaitable[Response]]
) -> Response:
    if request.method not in _SAFE:
        source = request.headers.get("origin") or request.headers.get("referer")
        if source:
            allowed = {request.headers.get("host", "").lower()} | {
                _netloc(o) for o in settings.cors_origins
            }
            if _netloc(source) not in allowed:
                return JSONResponse(
                    status_code=403, content={"detail": "cross-site request refused"}
                )
    return await call_next(request)
