"""SQLAlchemy ORM models.

All concrete models inherit from :class:`Base` (declared here) and live
in their own module.  Importing this package gives Alembic the full
metadata graph it needs for autogenerate.

P1 will populate this package with the entities from DESIGN.md §3.1.
"""

from __future__ import annotations

from sqlalchemy import MetaData
from sqlalchemy.orm import DeclarativeBase, MappedAsDataclass

# Naming convention so Alembic produces deterministic constraint names
NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}

metadata_obj = MetaData(naming_convention=NAMING_CONVENTION)


class Base(MappedAsDataclass, DeclarativeBase):
    """Common declarative base.

    ``MappedAsDataclass`` makes every model a dataclass — gives clean
    constructors and ``repr`` for free.  Subclasses opt into ``init=False``
    on fields that the DB fills (e.g. ``id`` autoincrement).
    """

    metadata = metadata_obj


# Concrete models — order matters only for readability; SQLAlchemy resolves
# inter-table relationships via string FKs.  Import every model module here
# so ``Base.metadata`` is fully populated for Alembic autogenerate.
from app.models.loan import Loan, LoanParty  # noqa: E402
from app.models.person import Person, PersonGuarantor  # noqa: E402
from app.models.topic import LoanTopic  # noqa: E402

__all__ = [
    "Base",
    "Loan",
    "LoanParty",
    "LoanTopic",
    "Person",
    "PersonGuarantor",
]
