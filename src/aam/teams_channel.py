"""Microsoft Teams delivery via Power Automate channel webhook (Path A).

Posts an Adaptive Card to a Teams channel through a Power Automate "When a
Teams webhook request is received" workflow. The workflow URL is the only
secret; no Azure permissions or Bot Framework registration required.

Adaptive Card schema:
  https://adaptivecards.io/explorer/AdaptiveCard.html
"""

from __future__ import annotations

import os
from typing import Any

import httpx
import structlog

log = structlog.get_logger()


def _webhook_url() -> str | None:
    return os.environ.get("AAM_TEAMS_WEBHOOK_URL")


def _build_card(*, am_email: str, narrative: str, actions: list[dict]) -> dict:
    """Build the AdaptiveCard payload the Power Automate workflow expects."""
    body: list[dict[str, Any]] = [
        {
            "type": "TextBlock",
            "text": f"Daily briefing — {am_email}",
            "size": "Large",
            "weight": "Bolder",
            "wrap": True,
        },
        {
            "type": "TextBlock",
            "text": narrative or "_No priority actions today._",
            "wrap": True,
            "spacing": "Small",
            "isSubtle": True,
        },
    ]

    for i, a in enumerate(actions, 1):
        is_risk = a["direction"] == "risk"
        body.append(
            {
                "type": "Container",
                "style": "attention" if is_risk else "good",
                "spacing": "Medium",
                "items": [
                    {
                        "type": "ColumnSet",
                        "columns": [
                            {
                                "type": "Column",
                                "width": "auto",
                                "items": [
                                    {
                                        "type": "TextBlock",
                                        "text": "RISK" if is_risk else "OPP",
                                        "weight": "Bolder",
                                        "size": "Small",
                                        "color": "Attention" if is_risk else "Good",
                                    }
                                ],
                            },
                            {
                                "type": "Column",
                                "width": "stretch",
                                "items": [
                                    {
                                        "type": "TextBlock",
                                        "text": (
                                            f"{i}. **{a['account']['name']}** "
                                            f"({a['account']['tier']}, "
                                            f"${int(a['account']['arr']):,} ARR)"
                                        ),
                                        "weight": "Bolder",
                                        "wrap": True,
                                    },
                                    {
                                        "type": "TextBlock",
                                        "text": (
                                            f"`{a['signal_kind']}` · "
                                            f"score {a['signal_score']:.2f} · "
                                            f"weighted {a['weighted_score']:.2f}"
                                        ),
                                        "isSubtle": True,
                                        "spacing": "None",
                                        "wrap": True,
                                    },
                                ],
                            },
                        ],
                    }
                ],
            }
        )

    return {
        "type": "message",
        "attachments": [
            {
                "contentType": "application/vnd.microsoft.card.adaptive",
                "contentUrl": None,
                "content": {
                    "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
                    "type": "AdaptiveCard",
                    "version": "1.4",
                    "body": body,
                },
            }
        ],
    }


async def post_briefing(*, am_email: str, narrative: str, actions: list[dict]) -> dict:
    url = _webhook_url()
    if not url:
        log.info("aam.teams.skipped", reason="no_webhook_url")
        return {"skipped": True, "reason": "no_webhook_url"}

    card = _build_card(am_email=am_email, narrative=narrative, actions=actions)
    async with httpx.AsyncClient(timeout=15.0) as c:
        r = await c.post(url, json=card)
    # Power Automate returns 202 Accepted with no body for successful workflow trigger
    if r.status_code in (200, 202):
        log.info("aam.teams.delivered", am=am_email, status=r.status_code)
        return {"ok": True, "status": r.status_code}
    log.warning(
        "aam.teams.delivery_failed",
        am=am_email,
        status=r.status_code,
        body=r.text[:300],
    )
    return {"ok": False, "status": r.status_code, "error": r.text[:300]}
