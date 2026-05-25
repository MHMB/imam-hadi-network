"""Typer CLI for the importer.

Stub for P0 — body implemented in P2.  Usage will be::

    python -m app.importer.cli sample.xlsm [more.xlsm ...]
"""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

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


@app.command()
def run(files: FilesArg, dry_run: DryRunOpt = False) -> None:
    """Import one or more .xlsm files into the database (P2)."""
    configure_logging()
    log.warning(
        "importer.not_implemented",
        files=[str(f) for f in files],
        dry_run=dry_run,
        note="Stub for P0. Real importer lands in P2.",
    )
    raise typer.Exit(code=2)


if __name__ == "__main__":  # pragma: no cover
    app()
