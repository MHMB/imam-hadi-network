"""The one definition of installment money, shared by every aggregate.

An installment can be paid in several parts, so "remaining" is never
"amount where unpaid": it is ``amount - amount_paid``.  Fully paid rows
contribute 0 remaining and their whole amount as paid.
"""

from __future__ import annotations

from typing import Any

from app.models import Installment

#: Still owed on an installment (0 once fully paid).
REMAINING: Any = Installment.amount - Installment.amount_paid
#: Already received on an installment.
PAID: Any = Installment.amount_paid


def remaining_of(table: Any) -> Any:
    """``REMAINING`` for an aliased installment table (``alias.c``)."""
    return table.c.amount - table.c.amount_paid
