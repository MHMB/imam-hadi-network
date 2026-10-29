"""رابط labels: list, link to a person (audited), applied to every loan, survives re-import."""

from __future__ import annotations

import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.integration


@pytest.mark.asyncio
async def test_link_liaison_label_to_person(seeded_client: AsyncClient) -> None:
    rows = (await seeded_client.get("/api/liaisons")).json()
    assert rows, "sample has رابط labels"
    label = rows[0]["label"]
    person = (await seeded_client.get("/api/persons?page_size=1")).json()["items"][0]

    r = await seeded_client.put("/api/liaisons", json={"label": label, "person_id": person["id"]})
    assert r.status_code == 200, r.text
    row = next(x for x in r.json() if x["label"] == label)
    assert row["confirmed"]
    assert row["person"]["id"] == person["id"]

    brokered = (await seeded_client.get(f"/api/persons/{person['id']}")).json()["brokered"]
    assert brokered["loan_count"] == rows[0]["loan_count"]
    assert (await seeded_client.get(f"/api/audit?entity=liaison&entity_id={person['id']}")).json()

    # «روابط»-style: mark the label as a channel → no person.
    r = await seeded_client.put("/api/liaisons", json={"label": label, "person_id": None})
    assert next(x for x in r.json() if x["label"] == label)["person"] is None


@pytest.mark.asyncio
async def test_link_unknown_person_is_422(seeded_client: AsyncClient) -> None:
    r = await seeded_client.put("/api/liaisons", json={"label": "x", "person_id": 999_999_999})
    assert r.status_code == 422
