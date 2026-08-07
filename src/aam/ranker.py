"""Weighted ranking of (account, signal) pairs per AM.

Weights are tunable via AM feedback; for v0 they're a static dict. A real
production version would persist weights per AM and update them when an AM
marks a briefing item as "wrong" (decrement) or "done & valuable" (increment).
"""

from __future__ import annotations

from dataclasses import dataclass

from aam.db import Account

# Default weights — risks higher than opportunities by default since
# missing a churn warning costs more than missing an upsell.
DEFAULT_WEIGHTS: dict[str, float] = {
    "ticket_velocity_risk": 1.00,
    "renewal_proximity": 0.95,
    "engagement_decay": 0.85,
    "usage_growth": 0.70,
    "cosell_fit": 0.60,
    "module_gap": 0.60,
    "doc_activity_decay": 0.50,
}


@dataclass
class RankedAction:
    account: Account
    signal_kind: str
    signal_score: float
    direction: str  # "risk" | "opportunity"
    weighted_score: float
    detail: dict


def rank_for_am(
    am_email: str,
    account_signals: list[tuple[Account, list[dict]]],
    *,
    weights: dict[str, float] | None = None,
    top_n: int = 5,
) -> list[RankedAction]:
    weights = weights or DEFAULT_WEIGHTS
    actions: list[RankedAction] = []
    for account, signals in account_signals:
        if account.am_email != am_email:
            continue
        for sig in signals:
            w = weights.get(sig["kind"], 0.5)
            actions.append(
                RankedAction(
                    account=account,
                    signal_kind=sig["kind"],
                    signal_score=sig["score"],
                    direction=sig["direction"],
                    weighted_score=round(sig["score"] * w, 4),
                    detail=sig["detail"],
                )
            )

    actions.sort(key=lambda a: a.weighted_score, reverse=True)
    return actions[:top_n]
