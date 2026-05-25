"""Typer CLI for the importer.

Usage::

    python -m app.importer.cli path/to/file.xlsm [more.xlsm ...]
    python -m app.importer.cli --dry-run path/to/file.xlsm

Exit codes:

    0  every file imported (or sha-deduped) without error-severity issues.
    1  at least one file produced one or more error-severity DataIssue
       rows.  The data still landed (Phase 1 contract: never block,
       always surface issues); admins should review and re-upload after
       fixing the xlsm.
    2  bad invocation (missing file etc).
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Annotated

import typer

from app.importer.runner import ImportOutcome, open_session, run_import
from app.logging import configure_logging, get_logger

app = typer.Typer(no_args_is_help=True, add_completion=False)
log = get_logger(__name__)

FilesArg = Annotated[
    list[Path],
    typer.Argument(exists=True, dir_okay=False, readable=True),
]
DryRunOpt = Annotated[
    bool,
    typer.Option("--dry-run", help="Parse + validate, write nothing."),
]
ReportPathOpt = Annotated[
    Path | None,
    typer.Option("--report", help="Write outcome JSON for all files to this path."),
]


@app.command()
def run(
    files: FilesArg,
    dry_run: DryRunOpt = False,
    report: ReportPathOpt = None,
) -> None:
    """Import one or more .xlsm files into the database."""
    configure_logging()
    outcomes = asyncio.run(_run_all(files, dry_run=dry_run))

    if report is not None:
        report.write_text(
            json.dumps([_outcome_to_dict(o) for o in outcomes], ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        log.info("importer.report_written", path=str(report))

    _print_summary(outcomes, dry_run=dry_run)

    if any(o.error_count for o in outcomes):
        raise typer.Exit(code=1)


async def _run_all(files: list[Path], *, dry_run: bool) -> list[ImportOutcome]:
    outcomes: list[ImportOutcome] = []
    async with open_session() as session:
        for f in files:
            outcomes.append(await run_import(session, f, dry_run=dry_run))
    return outcomes


def _print_summary(outcomes: list[ImportOutcome], *, dry_run: bool) -> None:
    banner = "DRY-RUN:" if dry_run else "OK:"
    for o in outcomes:
        prefix = "DEDUP" if o.deduped else banner
        typer.echo(
            f"{prefix} {o.file.name} → import_id={o.import_id} "
            f"years={o.years_imported} loans={o.loans} persons={o.persons} "
            f"issues={o.issues_total} (errors={o.error_count}) "
            f"in {o.duration_ms}ms"
        )
        if o.issues_by_severity:
            typer.echo(f"    by severity: {o.issues_by_severity}")
        if o.issues_by_category:
            typer.echo(f"    by category: {o.issues_by_category}")


def _outcome_to_dict(o: ImportOutcome) -> dict[str, object]:
    return {
        "file": str(o.file),
        "sha256": o.sha256,
        "import_id": o.import_id,
        "years_imported": o.years_imported,
        "loans": o.loans,
        "persons": o.persons,
        "topics_in_file": o.topics_in_file,
        "issues_total": o.issues_total,
        "issues_by_severity": o.issues_by_severity,
        "issues_by_category": o.issues_by_category,
        "error_count": o.error_count,
        "deduped": o.deduped,
        "duration_ms": o.duration_ms,
    }


if __name__ == "__main__":  # pragma: no cover
    app()
