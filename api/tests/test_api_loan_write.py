"""Creating loans: schedule generation, validation, numbering, edit + audit."""

from __future__ import annotations

from decimal import Decimal

import pytest
from httpx import AsyncClient

from app.schemas.loan_write import SchedulePreviewRequest
from app.services.loan_write import preview_schedule, split_equal

pytestmark = pytest.mark.integration


def test_split_equal_keeps_every_rial() -> None:
    parts = split_equal(Decimal("10"), 3)
    assert parts == [Decimal("3.333"), Decimal("3.333"), Decimal("3.334")]
    assert sum(parts) == Decimal("10")


def test_preview_is_pro_rata_and_exact() -> None:
    out = preview_schedule(
        SchedulePreviewRequest.model_validate(
            {
                "lenders": [{"person_id": 1, "amount": "3"}, {"person_id": 2, "amount": "2"}],
                "months": 4,
                "first_due": {"year": 1405, "month": 6, "day": 31},
            }
        )
    )
    a, b = out.lenders
    assert [i.amount for i in a.installments] == [Decimal("0.75")] * 4
    assert sum(i.amount for i in b.installments) == Decimal("2")
    # day 31 clamps to 30 from مهر on
    assert [(i.year, i.month, i.day) for i in a.installments] == [
        (1405, 6, 31),
        (1405, 7, 30),
        (1405, 8, 30),
        (1405, 9, 30),
    ]


def test_add_months_rolls_the_year_and_clamps_esfand() -> None:
    from app.jalali import add_months

    assert add_months(1405, 11, 30, 1) == (1405, 12, 29)  # 1405 is not leap
    assert add_months(1405, 12, 29, 1) == (1406, 1, 29)


async def _people(c: AsyncClient, n: int) -> list[int]:
    return [p["id"] for p in (await c.get(f"/api/persons?page_size={n}")).json()["items"]]


async def _topic(c: AsyncClient) -> int:
    return (await c.get("/api/topics")).json()[0]["id"]


@pytest.mark.asyncio
async def test_create_loan_end_to_end(seeded_client: AsyncClient) -> None:
    borrower, l1, l2 = await _people(seeded_client, 3)
    preview = (
        await seeded_client.post(
            "/api/loans/schedule-preview",
            json={
                "lenders": [{"person_id": l1, "amount": "3"}, {"person_id": l2, "amount": "2"}],
                "months": 5,
                "first_due": {"year": 1405, "month": 9, "day": 1},
            },
        )
    ).json()
    before = (
        await seeded_client.get("/api/loans?sort=loan_number&sort_dir=desc&page_size=1")
    ).json()

    r = await seeded_client.post(
        "/api/loans",
        json={
            "borrower_id": borrower,
            "topic_id": await _topic(seeded_client),
            "lenders": preview["lenders"],
            "source_platform": "bale",
            "description": "ضامن تلفنی تأیید کرد",
            "note_flagged": True,
            "issued": {"year": 1405, "month": 8, "day": 7},
        },
    )
    assert r.status_code == 201, r.text
    loan_id = r.json()["id"]
    d = (await seeded_client.get(f"/api/loans/{loan_id}")).json()
    assert d["loan"]["origin"] == "app"
    assert d["loan"]["loan_number"] == str(int(before["items"][0]["loan_number"]) + 1)
    assert d["loan"]["source_platform"] == "bale"
    assert d["loan"]["note_flagged"] is True
    assert d["loan"]["persian_year"] == 1405
    assert d["totals"]["total"] == "5.000"
    assert d["totals"]["remaining"] == "5.000"
    assert len(d["lenders"]) == 2
    assert all(len(ln["installments"]) == 5 for ln in d["lenders"])

    log = (await seeded_client.get(f"/api/audit?entity=loan&entity_id={loan_id}")).json()
    assert log[0]["action"] == "create"
    assert len(log[0]["after"]["installments"]) == 10

    # edit: unflag the note, audited with before/after
    r = await seeded_client.patch(f"/api/loans/{loan_id}", json={"note_flagged": False})
    assert r.status_code == 200
    assert r.json()["loan"]["note_flagged"] is False
    log = (await seeded_client.get(f"/api/audit?entity=loan&entity_id={loan_id}")).json()
    assert log[0]["action"] == "update"
    assert log[0]["before"]["note_flagged"] is True
    assert log[0]["after"]["note_flagged"] is False


@pytest.mark.asyncio
async def test_create_loan_rejects_bad_schedules(seeded_client: AsyncClient) -> None:
    borrower, l1 = await _people(seeded_client, 2)
    topic = await _topic(seeded_client)
    bad_sum = {
        "person_id": l1,
        "amount": "3",
        "installments": [{"year": 1405, "month": 9, "day": 1, "amount": "2"}],
    }
    r = await seeded_client.post(
        "/api/loans", json={"borrower_id": borrower, "topic_id": topic, "lenders": [bad_sum]}
    )
    assert r.status_code == 422
    assert r.json()["detail"][0]["loc"] == ["body", "lenders.0"]

    self_lend = {
        "person_id": borrower,
        "amount": "1",
        "installments": [{"year": 1405, "month": 9, "day": 1, "amount": "1"}],
    }
    r = await seeded_client.post(
        "/api/loans", json={"borrower_id": borrower, "topic_id": topic, "lenders": [self_lend]}
    )
    assert r.json()["detail"][0]["loc"] == ["body", "borrower_id"]

    bad_day = {
        "person_id": l1,
        "amount": "1",
        "installments": [{"year": 1405, "month": 12, "day": 30, "amount": "1"}],
    }
    r = await seeded_client.post(
        "/api/loans", json={"borrower_id": borrower, "topic_id": topic, "lenders": [bad_day]}
    )
    assert r.status_code == 422, "1405 is not a leap year: اسفند has 29 days"


@pytest.mark.asyncio
async def test_create_person(seeded_client: AsyncClient) -> None:
    r = await seeded_client.post(
        "/api/persons", json={"full_name": "عضو تازه", "phone": "09351112233"}
    )
    assert r.status_code == 201, r.text
    p = (await seeded_client.get(f"/api/persons/{r.json()['id']}")).json()["person"]
    assert p["phone"] == "+989351112233"


@pytest.mark.asyncio
async def test_borrower_cannot_guarantee_own_loan(seeded_client: AsyncClient) -> None:
    borrower, lender = await _people(seeded_client, 2)
    body = {
        "borrower_id": borrower,
        "topic_id": await _topic(seeded_client),
        "lenders": [
            {
                "person_id": lender,
                "amount": "2",
                "installments": [{"year": 1405, "month": 9, "day": 1, "amount": "2"}],
            }
        ],
    }
    r = await seeded_client.post("/api/loans", json={**body, "guarantor_id": borrower})
    assert r.status_code == 422
    assert r.json()["detail"][0]["loc"] == ["body", "guarantor_id"]

    loan_id = (await seeded_client.post("/api/loans", json=body)).json()["id"]
    r = await seeded_client.patch(f"/api/loans/{loan_id}", json={"guarantor_id": borrower})
    assert r.status_code == 422
    assert (
        await seeded_client.patch(f"/api/loans/{loan_id}", json={"guarantor_id": lender})
    ).status_code == 200


@pytest.mark.asyncio
async def test_loan_history_names_ids_and_lists_payments(seeded_client: AsyncClient) -> None:
    borrower, lender, guarantor = await _people(seeded_client, 3)
    topics = (await seeded_client.get("/api/topics")).json()
    body = {
        "borrower_id": borrower,
        "topic_id": topics[0]["id"],
        "lenders": [
            {
                "person_id": lender,
                "amount": "2",
                "installments": [{"year": 1405, "month": 9, "day": 1, "amount": "2"}],
            }
        ],
    }
    loan_id = (await seeded_client.post("/api/loans", json=body)).json()["id"]
    await seeded_client.patch(
        f"/api/loans/{loan_id}", json={"topic_id": topics[1]["id"], "guarantor_id": guarantor}
    )
    pay = {"amount": "1", "paid": {"year": 1405, "month": 8, "day": 7}}
    assert (await seeded_client.post(f"/api/loans/{loan_id}/payments", json=pay)).status_code == 201

    entries = (await seeded_client.get(f"/api/audit?entity=loan&entity_id={loan_id}")).json()
    assert [e["entity"] for e in entries][:1] == ["payment"]
    update = next(e for e in entries if e["action"] == "update")
    assert update["names"]["topic_id"][str(topics[1]["id"])] == topics[1]["name"]
    assert str(guarantor) in update["names"]["guarantor_id"]
