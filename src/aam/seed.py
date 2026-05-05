"""Synthetic seed data: 12 partner accounts engineered to surface every
briefing pattern (silently churning, expansion-ready, tier-promotable, healthy,
co-sell openings, P1 incident risk, renewal cliff)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

import structlog

from aam.db import Account, AccountSnapshot, init_db, session

log = structlog.get_logger()

ALICE = "alice@cyberco.com"
BOB = "bob@cyberco.com"
CARMEN = "carmen@cyberco.com"

NOW = datetime.now(timezone.utc).replace(tzinfo=None)


def _account(
    *, id: str, name: str, domain: str, tier: str, region: str,
    services: list[str], months_in: int, contract_months: int,
    arr: float, industry: str, am: str,
) -> Account:
    start = NOW - timedelta(days=30 * months_in)
    return Account(
        id=id, name=name, domain=domain, tier=tier, region=region,
        services_purchased=services,
        contract_start=start,
        contract_end=start + timedelta(days=30 * contract_months),
        arr=arr, industry=industry, am_email=am,
    )


def _snap(account_id: str, days_ago: int = 0, **overrides: Any) -> AccountSnapshot:
    base: dict[str, Any] = dict(
        account_id=account_id,
        captured_at=NOW - timedelta(days=days_ago),
        hubspot_emails_opened_30d=8,
        hubspot_meetings_30d=2,
        hubspot_last_activity_days_ago=4,
        zendesk_tickets_opened_30d=10,
        zendesk_tickets_closed_30d=9,
        zendesk_p1_count_30d=0,
        zendesk_avg_resolution_hours=8.0,
        zendesk_csat=4.5,
        portal_logins_30d=30,
        portal_modules_active=["soc-dashboard", "vuln-scanner"],
        portal_modules_unused=[],
        portal_last_login_days_ago=2,
        sharepoint_doc_views_30d=20,
    )
    base.update(overrides)
    return AccountSnapshot(**base)


# 12 accounts spanning every pattern AAM should surface
ACCOUNTS_PLAN: list[tuple[Account, list[AccountSnapshot]]] = [
    # 1. Silently churning — engagement decay, low logins, but no tickets (no obvious red flags)
    (
        _account(id="acct-001", name="Pinnacle Trust Bank", domain="pinnacle-trust.com",
                 tier="gold", region="NA", services=["managed-soc", "vuln-mgmt"],
                 months_in=14, contract_months=24, arr=120_000, industry="financial_services", am=ALICE),
        [
            _snap("acct-001", days_ago=60, hubspot_emails_opened_30d=18, portal_logins_30d=42, hubspot_last_activity_days_ago=2),
            _snap("acct-001", days_ago=30, hubspot_emails_opened_30d=10, portal_logins_30d=22, hubspot_last_activity_days_ago=8),
            _snap("acct-001", days_ago=0,  hubspot_emails_opened_30d=3,  portal_logins_30d=6,  hubspot_last_activity_days_ago=21,
                  portal_last_login_days_ago=18, sharepoint_doc_views_30d=2),
        ],
    ),
    # 2. Expansion-ready — usage growing, modules expanding, healthy tickets
    (
        _account(id="acct-002", name="Helix Biotech", domain="helixbio.com",
                 tier="silver", region="NA", services=["managed-soc"],
                 months_in=8, contract_months=12, arr=48_000, industry="healthcare", am=ALICE),
        [
            _snap("acct-002", days_ago=60, portal_logins_30d=22, portal_modules_active=["soc-dashboard"]),
            _snap("acct-002", days_ago=30, portal_logins_30d=48, portal_modules_active=["soc-dashboard", "vuln-scanner"]),
            _snap("acct-002", days_ago=0,  portal_logins_30d=92, portal_modules_active=["soc-dashboard", "vuln-scanner", "incident-tracker"],
                  hubspot_emails_opened_30d=24, hubspot_meetings_30d=5),
        ],
    ),
    # 3. Tier-promotion candidate — silver but using all gold features heavily
    (
        _account(id="acct-003", name="Arcadia Logistics", domain="arcadia-logistics.com",
                 tier="silver", region="EU", services=["managed-soc", "vuln-mgmt"],
                 months_in=10, contract_months=12, arr=52_000, industry="logistics", am=BOB),
        [
            _snap("acct-003", days_ago=30, portal_logins_30d=110, portal_modules_active=["soc-dashboard", "vuln-scanner", "incident-tracker", "compliance-reports"]),
            _snap("acct-003", days_ago=0,  portal_logins_30d=145, portal_modules_active=["soc-dashboard", "vuln-scanner", "incident-tracker", "compliance-reports"],
                  hubspot_meetings_30d=4, zendesk_tickets_opened_30d=22, zendesk_csat=4.8),
        ],
    ),
    # 4. P1 incident risk — high P1 count, slow resolution, falling CSAT
    (
        _account(id="acct-004", name="Vanguard Defense Systems", domain="vanguard-def.com",
                 tier="platinum", region="NA", services=["managed-soc", "incident-response", "vuln-mgmt"],
                 months_in=18, contract_months=36, arr=240_000, industry="defense", am=ALICE),
        [
            _snap("acct-004", days_ago=30, zendesk_p1_count_30d=2, zendesk_avg_resolution_hours=14, zendesk_csat=4.2),
            _snap("acct-004", days_ago=0,  zendesk_p1_count_30d=6, zendesk_avg_resolution_hours=28, zendesk_csat=3.1,
                  zendesk_tickets_opened_30d=42),
        ],
    ),
    # 5. Renewal cliff — contract ends in 45 days, decent usage but no renewal conversation
    (
        _account(id="acct-005", name="Meridian Insurance Group", domain="meridian-ins.com",
                 tier="gold", region="NA", services=["managed-soc", "compliance"],
                 months_in=11, contract_months=12, arr=96_000, industry="insurance", am=BOB),
        [
            _snap("acct-005", days_ago=30, hubspot_meetings_30d=2),
            _snap("acct-005", days_ago=0,  hubspot_meetings_30d=1, hubspot_last_activity_days_ago=12),
        ],
    ),
    # 6. Module gap — bought compliance module, never activated it
    (
        _account(id="acct-006", name="Northwind Energy", domain="northwind-energy.com",
                 tier="gold", region="NA", services=["managed-soc", "vuln-mgmt", "compliance-reports"],
                 months_in=6, contract_months=24, arr=110_000, industry="energy", am=CARMEN),
        [
            _snap("acct-006", days_ago=0, portal_modules_active=["soc-dashboard", "vuln-scanner"],
                  portal_modules_unused=["compliance-reports"], portal_logins_30d=58),
        ],
    ),
    # 7. Healthy steady — mention briefly, don't surface as priority
    (
        _account(id="acct-007", name="Beacon Health Network", domain="beacon-health.net",
                 tier="silver", region="NA", services=["managed-soc"],
                 months_in=7, contract_months=24, arr=42_000, industry="healthcare", am=CARMEN),
        [_snap("acct-007", days_ago=0)],
    ),
    # 8. Co-sell opening — defense industry vertical fit with #4 + active executive sponsor
    (
        _account(id="acct-008", name="Sentinel Aerospace", domain="sentinel-aero.com",
                 tier="gold", region="NA", services=["managed-soc", "vuln-mgmt"],
                 months_in=4, contract_months=24, arr=98_000, industry="defense", am=ALICE),
        [
            _snap("acct-008", days_ago=0, hubspot_meetings_30d=6, hubspot_emails_opened_30d=32,
                  portal_logins_30d=78),
        ],
    ),
    # 9. Quiet but stable — low engagement is normal for this account
    (
        _account(id="acct-009", name="Coastal Maritime Authority", domain="coastal-maritime.gov",
                 tier="bronze", region="NA", services=["managed-soc"],
                 months_in=20, contract_months=36, arr=24_000, industry="public_sector", am=BOB),
        [_snap("acct-009", days_ago=0, hubspot_emails_opened_30d=4, portal_logins_30d=12)],
    ),
    # 10. New account ramp — onboarded recently, increasing usage, expected
    (
        _account(id="acct-010", name="Aurora Robotics", domain="auroraroboticsai.com",
                 tier="silver", region="NA", services=["managed-soc", "vuln-mgmt"],
                 months_in=2, contract_months=12, arr=54_000, industry="manufacturing", am=CARMEN),
        [
            _snap("acct-010", days_ago=30, portal_logins_30d=12),
            _snap("acct-010", days_ago=0,  portal_logins_30d=38, hubspot_meetings_30d=3),
        ],
    ),
    # 11. Engagement decay + ticket spike — combined risk
    (
        _account(id="acct-011", name="Rivermark Fintech", domain="rivermark.io",
                 tier="gold", region="EU", services=["managed-soc", "vuln-mgmt", "incident-response"],
                 months_in=15, contract_months=24, arr=130_000, industry="financial_services", am=BOB),
        [
            _snap("acct-011", days_ago=60, hubspot_emails_opened_30d=20, zendesk_tickets_opened_30d=8),
            _snap("acct-011", days_ago=30, hubspot_emails_opened_30d=12, zendesk_tickets_opened_30d=18),
            _snap("acct-011", days_ago=0,  hubspot_emails_opened_30d=4,  zendesk_tickets_opened_30d=34,
                  zendesk_p1_count_30d=3, zendesk_csat=3.4, hubspot_last_activity_days_ago=14),
        ],
    ),
    # 12. Fully engaged power user — flat-out happy, no action needed
    (
        _account(id="acct-012", name="Citadel Asset Management", domain="citadel-am.com",
                 tier="platinum", region="NA", services=["managed-soc", "vuln-mgmt", "incident-response", "compliance-reports"],
                 months_in=22, contract_months=36, arr=280_000, industry="financial_services", am=ALICE),
        [_snap("acct-012", days_ago=0, portal_logins_30d=180, hubspot_meetings_30d=8,
                zendesk_csat=4.9, portal_modules_active=["soc-dashboard", "vuln-scanner", "incident-tracker", "compliance-reports"])],
    ),
]


async def seed() -> None:
    await init_db()
    async with session() as s:
        for account, snapshots in ACCOUNTS_PLAN:
            s.add(account)
            for snap in snapshots:
                s.add(snap)
    log.info("aam.seed.complete", accounts=len(ACCOUNTS_PLAN))
