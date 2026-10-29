"""Payments: schedule order, partial + carry-forward, credit, custom split, void, schedule edit."""

from __future__ import annotations

from decimal import Decimal

import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.integration

PAID_ON = {"year": 1405, "month": 8, "day": 7}


async def _loan(c: AsyncClient) -> dict:
    """3 months × (lender A 1 + lender B 1) = 6 million, created in the app."""
    borrower, a, b = [p["id"] for p in (await c.get("/api/persons?page_size=3")).json()["items"]]
    topic = (await c.get("/api/topics")).json()[0]["id"]
    preview = (
        await c.post(
            "/api/loans/schedule-preview",
            json={
                "lenders": [{"person_id": a, "amount": "3"}, {"person_id": b, "amount": "3"}],
                "months": 3,
                "first_due": {"year": 1405, "month": 7, "day": 1},
            },
        )
    ).json()
    loan_id = (
        await c.post(
            "/api/loans",
            json={"borrower_id": borrower, "topic_id": topic, "lenders": preview["lenders"]},
        )
    ).json()["id"]
    return (await c.get(f"/api/loans/{loan_id}")).json()


def _paid(detail: dict) -> list[str]:
    """amount_paid of every installment in schedule order (month, lender)."""
    rows = [
        (i["due_persian_month"], k, i["amount_paid"])
        for k, ln in enumerate(detail["lenders"])
        for i in ln["installments"]
    ]
    return [str(Decimal(p)) for _, _, p in sorted(rows)]


@pytest.mark.asyncio
async def test_overpayment_carries_to_next_installment(seeded_client: AsyncClient) -> None:
    d = await _loan(seeded_client)
    lid = d["loan"]["id"]
    preview = (
        await seeded_client.post(f"/api/loans/{lid}/payments/preview", json={"amount": "1.3"})
    ).json()
    assert [Decimal(a["amount"]) for a in preview["allocations"]] == [Decimal("1"), Decimal("0.3")]
    assert Decimal(preview["credit"]) == 0

    r = await seeded_client.post(
        f"/api/loans/{lid}/payments", json={"amount": "1.3", "paid": PAID_ON}
    )
    assert r.status_code == 201, r.text
    d = (await seeded_client.get(f"/api/loans/{lid}")).json()
    assert _paid(d) == ["1.000", "0.300", "0.000", "0.000", "0.000", "0.000"]
    assert d["totals"]["remaining"] == "4.700"
    first = next(i for i in d["lenders"][0]["installments"] if i["due_persian_month"] == 7)
    assert first["status"] == "paid"


@pytest.mark.asyncio
async def test_payment_above_balance_needs_confirmation(seeded_client: AsyncClient) -> None:
    lid = (await _loan(seeded_client))["loan"]["id"]
    r = await seeded_client.post(
        f"/api/loans/{lid}/payments", json={"amount": "8", "paid": PAID_ON}
    )
    assert r.status_code == 422
    assert r.json()["detail"][0]["type"] == "credit_needs_confirmation"

    r = await seeded_client.post(
        f"/api/loans/{lid}/payments", json={"amount": "8", "paid": PAID_ON, "confirm_credit": True}
    )
    assert r.status_code == 201
    assert Decimal(r.json()[0]["credit"]) == Decimal("2")
    d = (await seeded_client.get(f"/api/loans/{lid}")).json()
    assert d["totals"]["settled"] is True
    assert Decimal(d["totals"]["credit"]) == Decimal("2")


@pytest.mark.asyncio
async def test_admin_split_and_void(seeded_client: AsyncClient) -> None:
    d = await _loan(seeded_client)
    lid = d["loan"]["id"]
    last_b = d["lenders"][1]["installments"][-1]["id"]  # admin chooses lender B's last month
    r = await seeded_client.post(
        f"/api/loans/{lid}/payments",
        json={
            "amount": "1",
            "paid": PAID_ON,
            "allocations": [{"installment_id": last_b, "amount": "1"}],
        },
    )
    assert r.status_code == 201, r.text
    pay_id = r.json()[0]["id"]
    d = (await seeded_client.get(f"/api/loans/{lid}")).json()
    assert d["lenders"][1]["installments"][-1]["status"] == "paid"

    too_much = await seeded_client.post(
        f"/api/loans/{lid}/payments",
        json={
            "amount": "2",
            "paid": PAID_ON,
            "allocations": [{"installment_id": last_b, "amount": "2"}],
        },
    )
    assert too_much.status_code == 422

    v = await seeded_client.post(f"/api/payments/{pay_id}/void")
    assert v.status_code == 200
    assert v.json()[0]["voided_at"] is not None
    d = (await seeded_client.get(f"/api/loans/{lid}")).json()
    assert d["totals"]["remaining"] == "6.000"
    assert d["lenders"][1]["installments"][-1]["status"] == "unpaid"
    assert (await seeded_client.post(f"/api/payments/{pay_id}/void")).status_code == 422
    log = (await seeded_client.get(f"/api/audit?entity=payment&entity_id={pay_id}")).json()
    assert [e["action"] for e in log] == ["void", "create"]


@pytest.mark.asyncio
async def test_schedule_edit_protects_paid_money(seeded_client: AsyncClient) -> None:
    d = await _loan(seeded_client)
    lid = d["loan"]["id"]
    await seeded_client.post(f"/api/loans/{lid}/payments", json={"amount": "0.5", "paid": PAID_ON})
    d = (await seeded_client.get(f"/api/loans/{lid}")).json()
    a, b = d["lenders"]
    paid_row = a["installments"][0]
    b_part = {
        "party_id": b["party_id"],
        "installments": [
            {
                "id": x["id"],
                "year": x["due_persian_year"],
                "month": x["due_persian_month"],
                "day": x["due_day_of_month"],
                "amount": x["amount"],
            }
            for x in b["installments"]
        ],
    }

    # merge lender A's two unpaid months into one at آذر — allowed
    edit = {
        "lenders": [
            {
                "party_id": a["party_id"],
                "installments": [
                    {"id": paid_row["id"], "year": 1405, "month": 7, "day": 1, "amount": "1"},
                    {"year": 1405, "month": 9, "day": 15, "amount": "2"},
                ],
            },
            b_part,
        ]
    }
    r = await seeded_client.put(f"/api/loans/{lid}/schedule", json=edit)
    assert r.status_code == 200, r.text
    a2 = r.json()["lenders"][0]["installments"]
    assert [(i["due_persian_month"], i["amount"]) for i in a2] == [(7, "1.000"), (9, "2.000")]

    # cannot cut the partly paid installment below what was paid
    edit["lenders"][0]["installments"][0]["amount"] = "0.4"
    edit["lenders"][0]["installments"][1]["amount"] = "2.6"
    assert (await seeded_client.put(f"/api/loans/{lid}/schedule", json=edit)).status_code == 422
    # cannot drop it either
    edit["lenders"][0]["installments"] = [{"year": 1405, "month": 9, "day": 1, "amount": "3"}]
    assert (await seeded_client.put(f"/api/loans/{lid}/schedule", json=edit)).status_code == 422
    # rows must still sum to the lender's amount
    edit["lenders"][0]["installments"] = [
        {"id": paid_row["id"], "year": 1405, "month": 7, "day": 1, "amount": "1"}
    ]
    assert (await seeded_client.put(f"/api/loans/{lid}/schedule", json=edit)).status_code == 422


@pytest.mark.asyncio
async def test_partial_payment_moves_kpi(seeded_client: AsyncClient) -> None:
    before = Decimal((await seeded_client.get("/api/kpi")).json()["outstanding_total"])
    lid = (await _loan(seeded_client))["loan"]["id"]
    await seeded_client.post(f"/api/loans/{lid}/payments", json={"amount": "1.3", "paid": PAID_ON})
    after = Decimal((await seeded_client.get("/api/kpi")).json()["outstanding_total"])
    assert after == before + Decimal("6") - Decimal("1.3")


@pytest.mark.asyncio
async def test_payment_on_imported_loan_blocks_reimport_of_its_year(
    seeded_client: AsyncClient,
) -> None:
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

    from app.config import settings
    from app.importer.writer import years_with_app_data

    loan = next(
        ln
        for ln in (await seeded_client.get("/api/loans?status=active&page_size=50")).json()["items"]
    )
    r = await seeded_client.post(
        f"/api/loans/{loan['id']}/payments", json={"amount": "0.1", "paid": PAID_ON}
    )
    assert r.status_code == 201, r.text

    engine = create_async_engine(str(settings.database_url))
    async with async_sessionmaker(engine)() as s:
        assert await years_with_app_data(s, [1404, 1405]) == [loan["persian_year"]]
    await engine.dispose()


@pytest.mark.asyncio
async def test_schedule_edit_rejects_duplicates_and_missing_lenders(
    seeded_client: AsyncClient,
) -> None:
    d = await _loan(seeded_client)
    lid = d["loan"]["id"]
    a, b = d["lenders"]
    row = lambda i: {  # noqa: E731
        "id": i["id"],
        "year": i["due_persian_year"],
        "month": i["due_persian_month"],
        "day": i["due_day_of_month"],
        "amount": i["amount"],
    }
    a_rows = [row(i) for i in a["installments"]]
    b_rows = [row(i) for i in b["installments"]]
    url = f"/api/loans/{lid}/schedule"

    only_a = {"lenders": [{"party_id": a["party_id"], "installments": a_rows}]}
    assert (await seeded_client.put(url, json=only_a)).status_code == 422

    twice_a = {
        "lenders": [
            {"party_id": a["party_id"], "installments": a_rows},
            {"party_id": a["party_id"], "installments": a_rows},
            {"party_id": b["party_id"], "installments": b_rows},
        ]
    }
    assert (await seeded_client.put(url, json=twice_a)).status_code == 422

    same_id = dict(a_rows[0], amount="2")
    dup_rows = {
        "lenders": [
            {"party_id": a["party_id"], "installments": [same_id, dict(same_id, amount="1")]},
            {"party_id": b["party_id"], "installments": b_rows},
        ]
    }
    assert (await seeded_client.put(url, json=dup_rows)).status_code == 422


@pytest.mark.asyncio
async def test_completing_by_edit_keeps_paid_date_and_voided_history(
    seeded_client: AsyncClient,
) -> None:
    d = await _loan(seeded_client)
    lid = d["loan"]["id"]
    await seeded_client.post(f"/api/loans/{lid}/payments", json={"amount": "0.5", "paid": PAID_ON})
    d = (await seeded_client.get(f"/api/loans/{lid}")).json()
    a, b = d["lenders"]
    first = a["installments"][0]
    rest = a["installments"][1:]
    # shrink the partly paid installment to exactly what was paid -> becomes paid
    rows = [
        {"id": first["id"], "year": 1405, "month": 7, "day": 1, "amount": "0.5"},
        *[
            {
                "id": i["id"],
                "year": i["due_persian_year"],
                "month": i["due_persian_month"],
                "day": i["due_day_of_month"],
                "amount": i["amount"],
            }
            for i in rest
        ],
        {"year": 1405, "month": 10, "day": 1, "amount": "0.5"},
    ]
    b_rows = [
        {
            "id": i["id"],
            "year": i["due_persian_year"],
            "month": i["due_persian_month"],
            "day": i["due_day_of_month"],
            "amount": i["amount"],
        }
        for i in b["installments"]
    ]
    r = await seeded_client.put(
        f"/api/loans/{lid}/schedule",
        json={
            "lenders": [
                {"party_id": a["party_id"], "installments": rows},
                {"party_id": b["party_id"], "installments": b_rows},
            ]
        },
    )
    assert r.status_code == 200, r.text
    assert r.json()["lenders"][0]["installments"][0]["status"] == "paid"

    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

    from app.config import settings
    from app.models import Installment

    engine = create_async_engine(str(settings.database_url))
    async with async_sessionmaker(engine)() as s:
        inst = await s.get(Installment, first["id"])
        assert inst is not None
        assert (inst.paid_persian_year, inst.paid_persian_month, inst.paid_persian_day) == (
            1405,
            8,
            7,
        )
    await engine.dispose()

    # void the payment; the installment still has history, so it can't be dropped
    pay_id = (await seeded_client.get(f"/api/loans/{lid}/payments")).json()[0]["id"]
    await seeded_client.post(f"/api/payments/{pay_id}/void")
    d = (await seeded_client.get(f"/api/loans/{lid}")).json()
    a, b = d["lenders"]
    keep = [i for i in a["installments"] if i["id"] != first["id"]]
    rows = [
        {
            "id": i["id"],
            "year": i["due_persian_year"],
            "month": i["due_persian_month"],
            "day": i["due_day_of_month"],
            "amount": i["amount"],
        }
        for i in keep
    ] + [{"year": 1405, "month": 11, "day": 1, "amount": "0.5"}]
    r = await seeded_client.put(
        f"/api/loans/{lid}/schedule",
        json={
            "lenders": [
                {"party_id": a["party_id"], "installments": rows},
                {"party_id": b["party_id"], "installments": b_rows},
            ]
        },
    )
    assert r.status_code == 422
    assert (await seeded_client.get(f"/api/loans/{lid}/payments")).json()[0]["allocations"]


@pytest.mark.asyncio
async def test_editing_an_imported_loan_blocks_reimport_of_its_year(
    seeded_client: AsyncClient,
) -> None:
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

    from app.config import settings
    from app.importer.writer import years_with_app_data

    loan = (await seeded_client.get("/api/loans?page_size=1")).json()["items"][0]
    r = await seeded_client.patch(f"/api/loans/{loan['id']}", json={"note_flagged": True})
    assert r.status_code == 200
    engine = create_async_engine(str(settings.database_url))
    async with async_sessionmaker(engine)() as s:
        assert loan["persian_year"] in await years_with_app_data(s, [1404, 1405])
    await engine.dispose()
