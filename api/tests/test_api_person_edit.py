"""PATCH /api/persons/{id}: phone required + unique, bank, contacts, audit trail."""

from __future__ import annotations

import base64

import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.integration

AUTH = {"Authorization": "Basic " + base64.b64encode(b"tester:secret").decode()}


async def _two_people(c: AsyncClient) -> tuple[int, int]:
    items = (await c.get("/api/persons?page_size=2")).json()["items"]
    return items[0]["id"], items[1]["id"]


@pytest.mark.asyncio
async def test_me_reads_basic_auth_username(seeded_client: AsyncClient) -> None:
    assert (await seeded_client.get("/api/me", headers=AUTH)).json()["username"] == "tester"
    assert (await seeded_client.get("/api/me")).json()["username"] == "dev"


@pytest.mark.asyncio
async def test_edit_profile_and_history(seeded_client: AsyncClient) -> None:
    pid, _ = await _two_people(seeded_client)
    r = await seeded_client.patch(
        f"/api/persons/{pid}",
        headers=AUTH,
        json={
            "phone": "۰۹۱۲ ۱۲۳ ۴۵۶۷",
            "bank_account": "6037-9911-2233-4455",
            "contacts": [
                {"platform": "bale", "handle": "@ali", "is_default": False},
                {"platform": "telegram", "handle": "@ali_t", "is_default": False},
            ],
        },
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["person"]["phone"] == "+989121234567"
    assert body["profile"]["bank_account"] == "6037991122334455"
    defaults = [c for c in body["profile"]["contacts"] if c["is_default"]]
    assert [c["platform"] for c in defaults] == ["bale"], "first contact becomes default"

    log = (await seeded_client.get(f"/api/audit?entity=person&entity_id={pid}")).json()
    assert len(log) == 1
    assert log[0]["username"] == "tester"
    assert log[0]["after"]["phone"] == "+989121234567"
    assert log[0]["before"]["phone"] != log[0]["after"]["phone"]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("patch", "field"),
    [
        ({"phone": "123"}, "phone"),
        ({"phone": "09121234567", "bank_account": "abc"}, "bank_account"),
        (
            {
                "phone": "09121234567",
                "contacts": [
                    {"platform": "bale", "handle": "a", "is_default": True},
                    {"platform": "eitaa", "handle": "b", "is_default": True},
                ],
            },
            "contacts",
        ),
    ],
)
async def test_edit_profile_rejects_invalid(
    seeded_client: AsyncClient, patch: dict[str, object], field: str
) -> None:
    pid, _ = await _two_people(seeded_client)
    r = await seeded_client.patch(f"/api/persons/{pid}", json=patch)
    assert r.status_code == 422
    assert r.json()["detail"][0]["loc"] == ["body", field]


@pytest.mark.asyncio
async def test_phone_must_be_unique(seeded_client: AsyncClient) -> None:
    a, b = await _two_people(seeded_client)
    assert (
        await seeded_client.patch(f"/api/persons/{a}", json={"phone": "09121234567"})
    ).status_code == 200
    r = await seeded_client.patch(f"/api/persons/{b}", json={"phone": "+98 912 123 4567"})
    assert r.status_code == 422
    assert r.json()["detail"][0]["type"] == "duplicate"


@pytest.mark.asyncio
async def test_search_short_query_digits_and_phone(seeded_client: AsyncClient) -> None:
    """«تست» finds «تست-…» names; a digit in a name query doesn't match phones."""
    for name, phone in (
        ("تست-قرض‌گیرنده", "09990000001"),
        ("تست-قرض‌دهنده-۱", "09990000002"),
        ("تست-قرض‌دهنده-۲", "09990000003"),
    ):
        r = await seeded_client.post("/api/persons", json={"full_name": name, "phone": phone})
        assert r.status_code == 201, r.text

    async def names(q: str) -> list[str]:
        body = (await seeded_client.get("/api/persons", params={"q": q})).json()
        return [p["full_name"] for p in body["items"]]

    assert len(await names("تست")) == 3
    # ZWNJ typed or not, Persian digit typed or ASCII: same single match first.
    assert (await names("قرض‌دهنده-۲"))[0] == "تست-قرض‌دهنده-۲"
    assert (await names("قرضدهنده-2"))[0] == "تست-قرض‌دهنده-۲"
    assert len(await names("قرض‌دهنده-۲")) <= 3
    assert await names("۰۹۹۹۰۰۰۰۰۰۳") == ["تست-قرض‌دهنده-۲"]
    # A lone digit is a name search: only names containing it, not every phone.
    assert all(("2" in n or "۲" in n) for n in await names("2"))
