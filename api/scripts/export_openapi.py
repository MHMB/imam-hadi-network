"""Export the FastAPI app's OpenAPI 3.1 schema to a JSON file.

Used as the contract input for the Next.js frontend in P4+ (we run
``openapi-typescript`` against the file to generate the typed API
client).  Run from the api/ directory::

    uv run python scripts/export_openapi.py docs/openapi.json
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from app.main import app


def main(out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(app.openapi(), ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"wrote {out_path}")


if __name__ == "__main__":  # pragma: no cover
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("docs/openapi.json")
    main(path)
