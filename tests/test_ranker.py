from datetime import datetime, timedelta, timezone

from aam.db import Account
from aam.ranker import DEFAULT_WEIGHTS, rank_for_am

NOW = datetime.now(timezone.utc).replace(tzinfo=None)


def _acct(id, am):
    return Account(
        id=id, name=f"a{id}", domain="x.com", tier="silver", region="NA",
        services_purchased=[], contract_start=NOW, contract_end=NOW + timedelta(days=200),
        arr=10_000.0, industry="financial_services", am_email=am,
    )


def test_filters_by_am():
    a1 = _acct("1", "alice@x")
    a2 = _acct("2", "bob@x")
    pairs = [
        (a1, [{"kind": "ticket_velocity_risk", "score": 1.0, "direction": "risk", "detail": {}}]),
        (a2, [{"kind": "renewal_proximity", "score": 1.0, "direction": "risk", "detail": {}}]),
    ]
    r = rank_for_am("alice@x", pairs)
    assert len(r) == 1
    assert r[0].account.id == "1"


def test_weighting_orders_correctly():
    a = _acct("1", "alice@x")
    pairs = [
        (a, [
            {"kind": "module_gap",          "score": 1.0, "direction": "opportunity", "detail": {}},
            {"kind": "ticket_velocity_risk","score": 1.0, "direction": "risk",        "detail": {}},
        ]),
    ]
    r = rank_for_am("alice@x", pairs)
    # ticket_velocity_risk weight (1.0) > module_gap weight (0.6)
    assert r[0].signal_kind == "ticket_velocity_risk"
    assert r[1].signal_kind == "module_gap"


def test_top_n_caps_results():
    a = _acct("1", "alice@x")
    sigs = [{"kind": k, "score": 1.0, "direction": "risk", "detail": {}} for k in DEFAULT_WEIGHTS]
    r = rank_for_am("alice@x", [(a, sigs)], top_n=3)
    assert len(r) == 3
