"""Slack DM delivery for daily briefings.

Each AM gets the briefing posted as a DM from the AAM bot. AM-email-to-Slack
mapping is via the AAM_SLACK_RECIPIENT_<EMAIL_LOCALPART> env vars (uppercased,
@-stripped); falls back to AAM_SLACK_RECIPIENT_DEFAULT.

The bot needs scopes: chat:write, users:read, users:read.email.
"""

from __future__ import annotations

import os

import httpx
import structlog

log = structlog.get_logger()

SLACK_API = "https://slack.com/api"


class SlackError(RuntimeError):
    pass


def _token() -> str | None:
    return os.environ.get("AAM_SLACK_BOT_TOKEN")


def _recipient_for(am_email: str) -> str | None:
    """Resolve an AM email to a Slack handle / user id.

    Lookup order:
      1. AAM_SLACK_RECIPIENT_<UPPERCASE_LOCALPART>  (e.g. AAM_SLACK_RECIPIENT_ALICE)
      2. AAM_SLACK_RECIPIENT_DEFAULT
    """
    localpart = am_email.split("@", 1)[0].replace(".", "_").upper()
    return (
        os.environ.get(f"AAM_SLACK_RECIPIENT_{localpart}")
        or os.environ.get("AAM_SLACK_RECIPIENT_DEFAULT")
    )


async def _slack_post(method: str, json: dict, token: str) -> dict:
    async with httpx.AsyncClient(timeout=15.0) as c:
        r = await c.post(
            f"{SLACK_API}/{method}",
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json; charset=utf-8",
            },
            json=json,
        )
    data = r.json()
    if not data.get("ok"):
        raise SlackError(f"slack {method} failed: {data.get('error')!r} — {data}")
    return data


async def _resolve_user_id(handle_or_email: str, token: str) -> str:
    """Accepts a user id (Uxxxx), a handle (@anthony / anthony), or an email."""
    if handle_or_email.startswith("U") and handle_or_email[1:].isalnum():
        return handle_or_email

    if "@" in handle_or_email:
        # Email → user lookup
        async with httpx.AsyncClient(timeout=15.0) as c:
            r = await c.get(
                f"{SLACK_API}/users.lookupByEmail",
                headers={"Authorization": f"Bearer {token}"},
                params={"email": handle_or_email},
            )
        data = r.json()
        if data.get("ok"):
            return data["user"]["id"]
        raise SlackError(f"users.lookupByEmail failed for {handle_or_email}: {data.get('error')}")

    # Handle (anthony / @anthony) → users.list scan
    handle = handle_or_email.lstrip("@").lower()
    async with httpx.AsyncClient(timeout=20.0) as c:
        cursor = ""
        while True:
            r = await c.get(
                f"{SLACK_API}/users.list",
                headers={"Authorization": f"Bearer {token}"},
                params={"limit": 200, **({"cursor": cursor} if cursor else {})},
            )
            data = r.json()
            if not data.get("ok"):
                raise SlackError(f"users.list failed: {data.get('error')}")
            for u in data.get("members", []):
                if u.get("deleted"):
                    continue
                if (
                    (u.get("name") or "").lower() == handle
                    or (u.get("profile", {}).get("display_name") or "").lower() == handle
                    or (u.get("profile", {}).get("real_name") or "").lower() == handle
                ):
                    return u["id"]
            cursor = data.get("response_metadata", {}).get("next_cursor", "")
            if not cursor:
                break
    raise SlackError(f"no slack user matched handle/email {handle_or_email!r}")


async def send_briefing_dm(*, am_email: str, markdown: str, actions: list[dict]) -> dict:
    """Open a DM with the resolved user and post the briefing.

    Returns the Slack message metadata, or raises SlackError if delivery fails.
    """
    token = _token()
    if not token:
        log.info("aam.slack.skipped", reason="no_token")
        return {"skipped": True, "reason": "no_token"}

    recipient = _recipient_for(am_email)
    if not recipient:
        log.warning("aam.slack.skipped", reason="no_recipient_mapped", am=am_email)
        return {"skipped": True, "reason": "no_recipient_mapped"}

    user_id = await _resolve_user_id(recipient, token)

    # Open IM channel
    open_resp = await _slack_post("conversations.open", {"users": user_id}, token)
    channel_id = open_resp["channel"]["id"]

    # Slack mrkdwn != strict markdown. Strip a few things that don't render well.
    text = (
        markdown.replace("**", "*")  # bold
        .replace("\n# ", "\n*")  # h1 → bold (best we can do in mrkdwn)
        .replace("\n## ", "\n\n*")  # h2
    )

    # Build a Block Kit message: header, summary text, then a list of action blocks
    blocks: list[dict] = [
        {"type": "header", "text": {"type": "plain_text", "text": f"Daily briefing — {am_email}"}},
        {"type": "section", "text": {"type": "mrkdwn", "text": text[:2900]}},
    ]
    for i, a in enumerate(actions, 1):
        emoji = ":rotating_light:" if a["direction"] == "risk" else ":seedling:"
        blocks.append(
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": (
                        f"{emoji} *{i}. {a['account']['name']}* "
                        f"({a['account']['tier']}, ${int(a['account']['arr']):,} ARR) — "
                        f"`{a['signal_kind']}` (weighted {a['weighted_score']:.2f})"
                    ),
                },
            }
        )

    msg = await _slack_post(
        "chat.postMessage",
        {"channel": channel_id, "blocks": blocks, "text": f"Daily briefing — {am_email}"},
        token,
    )
    log.info("aam.slack.delivered", am=am_email, channel=channel_id, ts=msg.get("ts"))
    return msg
