"""End-to-end: seed → score → brief, asserting expected accounts surface per AM."""

from __future__ import annotations

import pytest

from aam.briefing import generate_briefing
from aam.scoring import score_all


@pytest.mark.asyncio
async def test_alice_briefing_surfaces_p1_risk_and_silent_churn(seeded_db):
    n = await score_all()
    assert n > 0
    final = await generate_briefing("alice@cyberco.com")
    actions = final["actions"]
    account_signal_pairs = {(a["account"]["id"], a["signal_kind"]) for a in actions}

    # Vanguard P1 risk should be #1 by weighted score
    assert actions[0]["account"]["id"] == "acct-004"
    assert actions[0]["signal_kind"] == "ticket_velocity_risk"

    # Silent churn caught
    assert ("acct-001", "engagement_decay") in account_signal_pairs

    # Expansion-ready account caught
    assert ("acct-002", "usage_growth") in account_signal_pairs


@pytest.mark.asyncio
async def test_bob_briefing_surfaces_renewal_cliff(seeded_db):
    await score_all()
    final = await generate_briefing("bob@cyberco.com")
    actions = final["actions"]
    # Meridian renewal cliff (acct-005) should be top because renewal weight is high
    assert actions[0]["account"]["id"] == "acct-005"
    assert actions[0]["signal_kind"] == "renewal_proximity"


@pytest.mark.asyncio
async def test_carmen_briefing_only_opportunities(seeded_db):
    await score_all()
    final = await generate_briefing("carmen@cyberco.com")
    actions = final["actions"]
    assert all(a["direction"] == "opportunity" for a in actions)
    # Module gap on Northwind should appear
    assert any(
        a["account"]["id"] == "acct-006" and a["signal_kind"] == "module_gap"
        for a in actions
    )


@pytest.mark.asyncio
async def test_briefing_persists_with_id(seeded_db):
    await score_all()
    final = await generate_briefing("alice@cyberco.com")
    # An event with kind=persisted should be present and carry the briefing id
    persisted = [e for e in final["events"] if e.get("kind") == "persisted"]
    assert persisted
    assert "briefing_id" in persisted[0]
