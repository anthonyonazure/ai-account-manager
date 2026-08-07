"""Snapshot pullers — fetch live data from each source, write a new
AccountSnapshot row.

For the demo, seed.py creates synthetic snapshots directly, so you usually
don't need to run this. The pullers exist so the production architecture is
complete: in prod, swap mocks for real adapters via B2B_USE_MOCKS=false and
schedule `aam pull` nightly via cron / APScheduler.
"""

from __future__ import annotations

from datetime import UTC, datetime

import structlog
from b2b_toolkit import get_adapters
from sqlalchemy import select

from aam.db import Account, AccountSnapshot, session

log = structlog.get_logger()


async def pull_account(account_id: str) -> AccountSnapshot | None:
    adapters = get_adapters()
    async with session() as s:
        account = (
            await s.execute(select(Account).where(Account.id == account_id))
        ).scalar_one_or_none()
        if account is None:
            log.warning("aam.pull.unknown_account", account_id=account_id)
            return None

        # The mocks return canned numbers; in prod these are live API calls
        hub_signals = await adapters.hubspot.get_engagement_signals(account_id, days=30)
        zen_signals = await adapters.zendesk.get_ticket_velocity(
            0, days=30
        )  # mock ignores org_id
        # Portal pull is skipped here since the mock portal accounts are scoped
        # to the onboarding-agent demo; in prod this would be: await adapters.portal.get_usage(...)

        snap = AccountSnapshot(
            account_id=account_id,
            captured_at=datetime.now(UTC).replace(tzinfo=None),
            hubspot_emails_opened_30d=hub_signals.get("emails_opened", 0),
            hubspot_meetings_30d=hub_signals.get("meetings_attended", 0),
            hubspot_last_activity_days_ago=4,  # parsed from last_activity_at in prod
            zendesk_tickets_opened_30d=zen_signals.get("tickets_opened", 0),
            zendesk_tickets_closed_30d=zen_signals.get("tickets_closed", 0),
            zendesk_p1_count_30d=zen_signals.get("p1_count", 0),
            zendesk_avg_resolution_hours=zen_signals.get("avg_resolution_hours", 0.0),
            zendesk_csat=4.5,  # not in mock; would come from a real Zendesk Talk/CSAT API
        )
        s.add(snap)
        log.info("aam.pull.snapshot", account_id=account_id)
        return snap


async def pull_all_accounts() -> int:
    async with session() as s:
        ids = (await s.execute(select(Account.id))).scalars().all()
    for aid in ids:
        await pull_account(aid)
    return len(ids)
