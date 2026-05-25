"""xlsm upload service.

Owns the multipart-upload → on-disk save → background-import flow:

1. Stream the upload to a temp file (so RAM doesn't bloat on large xlsm).
2. Compute sha256 from the saved file.
3. Sha-dedup: if a successful Import with the same sha exists, return it
   without re-running the parser.
4. Otherwise: create a fresh ``Import`` row with ``status=pending``,
   return its id immediately, and schedule a background task that
   parses + validates + writes (using ``writer.apply_to_existing_import``).

The background task uses a brand-new async session because the request's
session is closed by the time it runs.
"""

from __future__ import annotations

import hashlib
import shutil
import tempfile
import time
from pathlib import Path

from fastapi import UploadFile
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.importer.runner import open_session, parse_workbook
from app.importer.validation import validate
from app.importer.writer import apply_to_existing_import
from app.logging import get_logger
from app.models import Import
from app.models.enums import ImportStatus

log = get_logger(__name__)


class UploadTooLarge(Exception):
    """413 — file exceeds settings.max_upload_mb."""


class NotAnXlsm(Exception):
    """415 — content type / suffix not xlsm."""


def _is_xlsm_filename(name: str) -> bool:
    return name.lower().endswith(".xlsm")


async def save_upload_and_register(
    session: AsyncSession,
    upload: UploadFile,
) -> tuple[Import, bool, Path | None]:
    """Stream-save the upload, register an Import row, return (row, was_deduped, file_path_if_needs_processing).

    - ``was_deduped=True`` → existing successful Import was returned; the
      caller should skip the background task.  ``file_path`` is ``None``.
    - ``was_deduped=False`` → row is brand new with status=pending; caller
      must schedule the background task with ``file_path``.
    """
    if not upload.filename or not _is_xlsm_filename(upload.filename):
        raise NotAnXlsm(f"expected .xlsm, got {upload.filename!r}")

    settings.upload_dir.mkdir(parents=True, exist_ok=True)
    max_bytes = settings.max_upload_mb * 1024 * 1024

    # --- stream to a temp file while hashing ---
    h = hashlib.sha256()
    written = 0
    with tempfile.NamedTemporaryFile(delete=False, dir=str(settings.upload_dir)) as tmp:
        while chunk := await upload.read(1 << 20):  # 1 MiB chunks
            written += len(chunk)
            if written > max_bytes:
                tmp.close()
                Path(tmp.name).unlink(missing_ok=True)
                raise UploadTooLarge(
                    f"upload {upload.filename!r} exceeded {settings.max_upload_mb} MB"
                )
            h.update(chunk)
            tmp.write(chunk)
        tmp_path = Path(tmp.name)

    sha = h.hexdigest()

    # --- sha-dedup: already processed? ---
    existing = (
        await session.execute(select(Import).where(Import.source_sha256 == sha))
    ).scalar_one_or_none()
    if existing is not None and existing.status is ImportStatus.success:
        tmp_path.unlink(missing_ok=True)  # already on disk under canonical name
        log.info("upload.dedup", sha256=sha, import_id=existing.id, filename=upload.filename)
        return existing, True, None

    # --- canonicalize file name + move into place ---
    final_path = settings.upload_dir / f"{sha}.xlsm"
    if final_path.exists():
        tmp_path.unlink(missing_ok=True)
    else:
        shutil.move(str(tmp_path), str(final_path))

    # If an existing row was pending/failed, reuse it (avoids unique constraint).
    if existing is not None:
        existing.source_filename = upload.filename
        existing.status = ImportStatus.pending
        existing.error_message = None
        await session.flush()
        log.info("upload.requeue", sha256=sha, import_id=existing.id, filename=upload.filename)
        return existing, False, final_path

    row = Import(
        source_sha256=sha,
        source_filename=upload.filename,
        years_imported=[],
        status=ImportStatus.pending,
        report={},
    )
    session.add(row)
    await session.flush()
    log.info("upload.queued", sha256=sha, import_id=row.id, filename=upload.filename)
    return row, False, final_path


async def process_pending_import(import_id: int, file_path: Path) -> None:
    """Background-task body: parse + validate + write into the pending row.

    Opens its own session because the request session is closed by the time
    BackgroundTasks runs us.  Any failure is captured on the Import row
    (status=failed, error_message=...) — never re-raised.
    """
    started = time.monotonic()
    # Mark running in one short-lived session so the long parse+write below
    # can use a fresh session without stale relationship-load surprises.
    async with open_session() as session:
        await session.execute(
            update(Import).where(Import.id == import_id).values(status=ImportStatus.running)
        )
        await session.commit()

    error_message: str | None = None
    loan_count = 0
    try:
        result = parse_workbook(file_path)
        validate(result)
    except Exception as exc:
        error_message = str(exc)[:2000]
        log.exception("import.parse_failed", import_id=import_id, error=str(exc))
    else:
        try:
            async with open_session() as session:
                imp = await session.get(Import, import_id)
                if imp is None:
                    log.error("import.process_missing_row", import_id=import_id)
                    return
                duration_ms = int((time.monotonic() - started) * 1000)
                await apply_to_existing_import(session, imp, result, duration_ms=duration_ms)
                loan_count = len(result.loans)
        except Exception as exc:
            error_message = str(exc)[:2000]
            log.exception("import.write_failed", import_id=import_id, error=str(exc))

    if error_message is not None:
        async with open_session() as session:
            await session.execute(
                update(Import)
                .where(Import.id == import_id)
                .values(
                    status=ImportStatus.failed,
                    error_message=error_message,
                    duration_ms=int((time.monotonic() - started) * 1000),
                )
            )
            await session.commit()
    else:
        log.info(
            "import.process_done",
            import_id=import_id,
            duration_ms=int((time.monotonic() - started) * 1000),
            loans=loan_count,
        )
