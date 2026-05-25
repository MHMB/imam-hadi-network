"""seed loan topics catalog

Revision ID: eed4758dd061
Revises: e934947a132b
Create Date: 2026-05-25 09:24:29.404426

Seeds the 17 topic names found on the legacy ``موضوعات`` sheet so the
importer can resolve every topic reference on first run.  Topics not in
this seed but present in newer xlsm files are upserted by the importer
(P2) — this list is the floor, not the ceiling.

Idempotent: uses ``ON CONFLICT (name) DO NOTHING`` so re-running this
migration on a partially-populated DB is safe.
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "eed4758dd061"
down_revision: str | None = "e934947a132b"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


# Order matches the legacy ``موضوعات`` sheet (SPEC.md §2.3).
# Only "نامعلوم" carries a legacy_num (0); the rest leave it NULL.
TOPICS: list[tuple[str, int | None]] = [
    ("از کار افتادگی", None),
    ("ازدواج", None),
    ("آموزشی", None),
    ("بدهی", None),
    ("تولد فرزند", None),
    ("خانه", None),
    ("درمان", None),
    ("زیارت", None),
    ("عتبات", None),
    ("کار فرهنگی", None),
    ("کالای دیجیتال", None),
    ("کسب و کار", None),
    ("نامعلوم", 0),
    ("وسیله نقلیه", None),
    ("امور جاری", None),
    ("وام", None),
    ("سرمایه گذاری", None),
]


def upgrade() -> None:
    loan_topic = sa.table(
        "loan_topic",
        sa.column("name", sa.String),
        sa.column("legacy_num", sa.Integer),
    )
    rows = [{"name": name, "legacy_num": legacy} for name, legacy in TOPICS]
    # Bulk insert + ON CONFLICT DO NOTHING for idempotency.  Using raw SQL
    # here rather than op.bulk_insert because op.bulk_insert lacks an
    # ON CONFLICT escape hatch.
    conn = op.get_bind()
    for row in rows:
        conn.execute(
            sa.text(
                "INSERT INTO loan_topic (name, legacy_num) "
                "VALUES (:name, :legacy_num) "
                "ON CONFLICT (name) DO NOTHING"
            ),
            row,
        )
    # silence linter on unused import (table descriptor) — we kept it
    # for clarity even though the loop uses raw SQL.
    del loan_topic


def downgrade() -> None:
    # Remove only the names we seeded; leave any importer-added topics alone.
    conn = op.get_bind()
    names = [name for name, _ in TOPICS]
    conn.execute(
        sa.text("DELETE FROM loan_topic WHERE name = ANY(:names)"),
        {"names": names},
    )
