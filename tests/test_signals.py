"""Pure-logic tests for the deterministic signal computers."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from aam.db import Account, AccountSnapshot
from aam.signals import (
    cosell_fit,
    doc_activity_decay,
    engagement_decay,
    module_gap,
    renewal_proximity,
    ticket_velocity_risk,
    usage_growth,
)

NOW = datetime.now(UTC).replace(tzinfo=None)


def _account(**over):
    base = {
        "id": "t1",
        "name": "T",
        "domain": "t.com",
        "tier": "silver",
        "region": "NA",
        "services_purchased": ["managed-soc"],
        "contract_start": NOW - timedelta(days=200),
        "contract_end": NOW + timedelta(days=200),
        "arr": 50_000.0,
        "industry": "financial_services",
        "am_email": "a@x",
    }
    base.update(over)
    return Account(**base)


def _snap(days_ago=0, **over):
    base = {
        "account_id": "t1",
        "captured_at": NOW - timedelta(days=days_ago),
        "hubspot_emails_opened_30d": 10,
        "hubspot_meetings_30d": 2,
        "hubspot_last_activity_days_ago": 4,
        "zendesk_tickets_opened_30d": 10,
        "zendesk_tickets_closed_30d": 10,
        "zendesk_p1_count_30d": 0,
        "zendesk_avg_resolution_hours": 8.0,
        "zendesk_csat": 4.5,
        "portal_logins_30d": 30,
        "portal_modules_active": ["soc-dashboard"],
        "portal_modules_unused": [],
        "portal_last_login_days_ago": 2,
        "sharepoint_doc_views_30d": 15,
    }
    base.update(over)
    return AccountSnapshot(**base)


def test_engagement_decay_fires_on_drop():
    a = _account()
    snaps = [
        _snap(days_ago=60, hubspot_emails_opened_30d=20),
        _snap(days_ago=0, hubspot_emails_opened_30d=4),
    ]
    s = engagement_decay(a, snaps)
    assert s and s["direction"] == "risk"
    assert s["score"] >= 0.6


def test_engagement_decay_silent_on_stable():
    a = _account()
    snaps = [
        _snap(days_ago=60, hubspot_emails_opened_30d=15),
        _snap(days_ago=0, hubspot_emails_opened_30d=14),
    ]
    assert engagement_decay(a, snaps) is None


def test_ticket_velocity_risk_high_p1():
    a = _account()
    s = ticket_velocity_risk(a, [_snap(zendesk_p1_count_30d=5, zendesk_csat=3.0)])
    assert s and s["score"] >= 0.7


def test_ticket_velocity_risk_silent_when_healthy():
    a = _account()
    assert ticket_velocity_risk(a, [_snap()]) is None


def test_usage_growth():
    a = _account()
    snaps = [
        _snap(days_ago=60, portal_logins_30d=20, portal_modules_active=["a"]),
        _snap(days_ago=0, portal_logins_30d=80, portal_modules_active=["a", "b", "c"]),
    ]
    s = usage_growth(a, snaps)
    assert s and s["direction"] == "opportunity"
    assert s["detail"]["modules_added"] == 2


def test_module_gap():
    a = _account()
    s = module_gap(a, [_snap(portal_modules_unused=["compliance-reports"])])
    assert s and s["direction"] == "opportunity"
    assert "compliance-reports" in s["detail"]["unused_modules"]


def test_renewal_proximity_within_30d():
    a = _account(
        contract_start=NOW - timedelta(days=340), contract_end=NOW + timedelta(days=20)
    )
    s = renewal_proximity(a, [_snap()])
    assert s and s["score"] >= 0.9
    assert s["direction"] == "risk"


def test_renewal_proximity_silent_when_far():
    a = _account(contract_end=NOW + timedelta(days=200))
    assert renewal_proximity(a, [_snap()]) is None


def test_doc_activity_decay():
    a = _account()
    s = doc_activity_decay(
        a,
        [
            _snap(days_ago=60, sharepoint_doc_views_30d=20),
            _snap(sharepoint_doc_views_30d=2),
        ],
    )
    assert s and s["direction"] == "risk"


def test_cosell_fit_with_healthy_peers():
    a = _account(industry="defense")
    s = cosell_fit(
        a,
        [_snap(portal_logins_30d=80)],
        healthy_peers_by_industry={"defense": ["other-1"]},
    )
    assert s and s["direction"] == "opportunity"


def test_cosell_fit_silent_without_peers():
    a = _account(industry="defense")
    assert cosell_fit(a, [_snap()], healthy_peers_by_industry={}) is None
