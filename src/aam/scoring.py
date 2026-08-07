"""Orchestrates: load latest snapshots → compute signals → persist Signal rows."""

from __future__ import annotations

from collections import defaultdict
from datetime import UTC, datetime

import structlog
from sqlalchemy import delete, select

from aam.db import Account, AccountSnapshot, Signal, session
from aam.signals import (  # noqa: F401  (kinds exported for callers)
    SIGNAL_KINDS,
    compute_all,
)

log = structlog.get_logger()

HEALTHY_INDUSTRY_THRESHOLD_LOGINS = 60
HEALTHY_INDUSTRY_THRESHOLD_CSAT = 4.5


async def _build_healthy_peers_map(
    accounts: list[Account], snaps_by_account: dict[str, list[AccountSnapshot]]
) -> dict[str, list[str]]:
    """Industry → list of healthy account ids in that industry."""
    healthy_by_industry: dict[str, list[str]] = defaultdict(list)
    for a in accounts:
        snaps = snaps_by_account.get(a.id, [])
        if not snaps:
            continue
        last = max(snaps, key=lambda s: s.captured_at)
        if (
            last.portal_logins_30d >= HEALTHY_INDUSTRY_THRESHOLD_LOGINS
            and last.zendesk_csat >= HEALTHY_INDUSTRY_THRESHOLD_CSAT
            and a.tier in ("gold", "platinum")
        ):
            healthy_by_industry[a.industry].append(a.id)
    return dict(healthy_by_industry)


async def score_all() -> int:
    """Compute every signal for every account from the most recent snapshots,
    persist Signal rows. Returns count of signals computed."""
    async with session() as s:
        accounts = (await s.execute(select(Account))).scalars().all()
        snaps = (await s.execute(select(AccountSnapshot))).scalars().all()

        snaps_by_account: dict[str, list[AccountSnapshot]] = defaultdict(list)
        for sn in snaps:
            snaps_by_account[sn.account_id].append(sn)

        peers_map = await _build_healthy_peers_map(list(accounts), snaps_by_account)

        n_signals = 0
        for account in accounts:
            account_snaps = snaps_by_account.get(account.id, [])
            if not account_snaps:
                continue
            latest_snap = max(account_snaps, key=lambda s: s.captured_at)
            # Idempotency: clear any prior signals for this snapshot before inserting
            await s.execute(delete(Signal).where(Signal.snapshot_id == latest_snap.id))
            for sig in compute_all(
                account, account_snaps, healthy_peers_by_industry=peers_map
            ):
                s.add(
                    Signal(
                        account_id=account.id,
                        snapshot_id=latest_snap.id,
                        kind=sig["kind"],
                        score=sig["score"],
                        direction=sig["direction"],
                        detail=sig["detail"],
                        computed_at=datetime.now(UTC).replace(tzinfo=None),
                    )
                )
                n_signals += 1

    log.info("aam.score.complete", signals=n_signals)
    return n_signals


async def latest_signals_per_account() -> list[tuple[Account, list[dict]]]:
    """Load the most recent set of signals for each account (per kind, latest)."""
    async with session() as s:
        accounts = (await s.execute(select(Account))).scalars().all()
        all_signals = (await s.execute(select(Signal))).scalars().all()

    # Bucket by (account_id, kind) → keep latest only
    latest: dict[tuple[str, str], Signal] = {}
    for sig in all_signals:
        key = (sig.account_id, sig.kind)
        if key not in latest or sig.computed_at > latest[key].computed_at:
            latest[key] = sig

    by_account: dict[str, list[dict]] = defaultdict(list)
    for (acct_id, _), sig in latest.items():
        by_account[acct_id].append(
            {
                "kind": sig.kind,
                "score": sig.score,
                "direction": sig.direction,
                "detail": sig.detail,
            }
        )

    return [(a, by_account.get(a.id, [])) for a in accounts]
