"""Deterministic signal computers. No LLM — math should not be hallucinated.

Each computer takes (account, snapshots[]) where snapshots are ordered oldest→newest,
and returns a Signal-shape dict. Score is normalized to 0.0..1.0.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from datetime import UTC, datetime

from aam.db import Account, AccountSnapshot

SIGNAL_KINDS = (
    "engagement_decay",
    "ticket_velocity_risk",
    "usage_growth",
    "module_gap",
    "renewal_proximity",
    "doc_activity_decay",
    "cosell_fit",
)


def _latest(snaps: list[AccountSnapshot]) -> AccountSnapshot:
    return max(snaps, key=lambda s: s.captured_at)


def _trend(values: Sequence[float]) -> float:
    """Return % change from first to last value, clamped to [-1, 1]."""
    if len(values) < 2 or values[0] == 0:
        return 0.0
    delta = (values[-1] - values[0]) / max(values[0], 1)
    return max(-1.0, min(1.0, delta))


def engagement_decay(account: Account, snaps: list[AccountSnapshot]) -> dict | None:
    if len(snaps) < 2:
        return None
    series = [
        s.hubspot_emails_opened_30d for s in sorted(snaps, key=lambda s: s.captured_at)
    ]
    trend = _trend(series)  # negative = decay
    if trend > -0.3:
        return None
    score = min(1.0, abs(trend))
    last = _latest(snaps)
    return {
        "kind": "engagement_decay",
        "score": round(score, 3),
        "direction": "risk",
        "detail": {
            "emails_opened_series": series,
            "trend_pct": round(trend, 3),
            "last_activity_days_ago": last.hubspot_last_activity_days_ago,
        },
    }


def ticket_velocity_risk(account: Account, snaps: list[AccountSnapshot]) -> dict | None:
    last = _latest(snaps)
    p1 = last.zendesk_p1_count_30d
    res_hours = last.zendesk_avg_resolution_hours
    csat = last.zendesk_csat
    # Composite: each component contributes
    p1_score = min(1.0, p1 / 5)
    res_score = min(1.0, max(0, res_hours - 12) / 24)
    csat_score = max(0, (4.0 - csat) / 2)  # csat below 4.0 is concerning
    score = max(p1_score, res_score, csat_score)
    if score < 0.3:
        return None
    return {
        "kind": "ticket_velocity_risk",
        "score": round(score, 3),
        "direction": "risk",
        "detail": {
            "p1_count_30d": p1,
            "avg_resolution_hours": res_hours,
            "csat": csat,
            "tickets_opened_30d": last.zendesk_tickets_opened_30d,
        },
    }


def usage_growth(account: Account, snaps: list[AccountSnapshot]) -> dict | None:
    if len(snaps) < 2:
        return None
    sorted_snaps = sorted(snaps, key=lambda s: s.captured_at)
    series = [s.portal_logins_30d for s in sorted_snaps]
    trend = _trend(series)
    module_growth = len(sorted_snaps[-1].portal_modules_active) - len(
        sorted_snaps[0].portal_modules_active
    )
    if trend < 0.5 and module_growth <= 0:
        return None
    score = min(1.0, max(trend, module_growth * 0.4))
    return {
        "kind": "usage_growth",
        "score": round(score, 3),
        "direction": "opportunity",
        "detail": {
            "logins_series": series,
            "trend_pct": round(trend, 3),
            "modules_added": module_growth,
            "current_modules": sorted_snaps[-1].portal_modules_active,
        },
    }


def module_gap(account: Account, snaps: list[AccountSnapshot]) -> dict | None:
    last = _latest(snaps)
    unused = last.portal_modules_unused
    if not unused:
        return None
    return {
        "kind": "module_gap",
        "score": min(1.0, len(unused) * 0.5),
        "direction": "opportunity",
        "detail": {
            "unused_modules": unused,
            "active_modules": last.portal_modules_active,
        },
    }


def renewal_proximity(account: Account, snaps: list[AccountSnapshot]) -> dict | None:
    days_to_renewal = (
        account.contract_end - datetime.now(UTC).replace(tzinfo=None)
    ).days
    if days_to_renewal > 90:
        return None
    if days_to_renewal < 0:
        score = 1.0
    elif days_to_renewal <= 30:
        score = 0.95
    elif days_to_renewal <= 60:
        score = 0.7
    else:
        score = 0.45
    return {
        "kind": "renewal_proximity",
        "score": score,
        "direction": "risk",
        "detail": {
            "days_to_renewal": days_to_renewal,
            "arr_at_risk": account.arr,
            "contract_end": account.contract_end.isoformat(),
        },
    }


def doc_activity_decay(account: Account, snaps: list[AccountSnapshot]) -> dict | None:
    if len(snaps) < 2:
        return None
    sorted_snaps = sorted(snaps, key=lambda s: s.captured_at)
    series = [s.sharepoint_doc_views_30d for s in sorted_snaps]
    trend = _trend(series)
    if trend > -0.5:
        return None
    return {
        "kind": "doc_activity_decay",
        "score": min(1.0, abs(trend)),
        "direction": "risk",
        "detail": {"views_series": series, "trend_pct": round(trend, 3)},
    }


def cosell_fit(
    account: Account,
    snaps: list[AccountSnapshot],
    *,
    healthy_peers_by_industry: dict[str, list[str]],
) -> dict | None:
    """Co-sell openings: another account in the same industry is healthy and growing.
    Could open warm intros, joint case studies, or industry-specific feature dev."""
    peers = [
        p
        for p in healthy_peers_by_industry.get(account.industry, [])
        if p != account.id
    ]
    if not peers:
        return None
    last = _latest(snaps)
    # Only fire for accounts that themselves have decent engagement to leverage
    if last.portal_logins_30d < 30:
        return None
    return {
        "kind": "cosell_fit",
        "score": min(1.0, len(peers) * 0.35 + 0.3),
        "direction": "opportunity",
        "detail": {"industry": account.industry, "peer_account_ids": peers},
    }


def compute_all(
    account: Account,
    snaps: list[AccountSnapshot],
    *,
    healthy_peers_by_industry: dict[str, list[str]] | None = None,
) -> Iterable[dict]:
    """Run every computer; yield non-None results."""
    healthy_peers_by_industry = healthy_peers_by_industry or {}
    for computer in (
        engagement_decay,
        ticket_velocity_risk,
        usage_growth,
        module_gap,
        renewal_proximity,
        doc_activity_decay,
    ):
        result = computer(account, snaps)
        if result is not None:
            yield result
    cs = cosell_fit(account, snaps, healthy_peers_by_industry=healthy_peers_by_industry)
    if cs is not None:
        yield cs
