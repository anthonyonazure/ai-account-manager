"""FastAPI Bot Framework endpoint at /api/messages.

This is the URL you give Azure Bot Service as your "messaging endpoint":
  https://<your-public-host>/api/messages

The bot does ~nothing except capture ConversationReferences when AMs install
or message it. AAM's actual outbound messaging is via aam.teams_dm.send_proactive_dm.

In production this needs to be reachable from Azure (use ngrok / cloudflared
during dev, or deploy as a small container behind your normal ingress).
"""

from __future__ import annotations

import os

import structlog
from botbuilder.core import (
    ActivityHandler,
    BotFrameworkAdapter,
    BotFrameworkAdapterSettings,
    TurnContext,
)
from botbuilder.schema import Activity, ChannelAccount
from fastapi import FastAPI, HTTPException, Request, Response

from aam.teams_dm import store_conversation_ref

log = structlog.get_logger()


async def _default_aad_resolver(aad_object_id: str) -> str | None:
    """Map an AAD object id to an AM email.

    Default impl: read AAM_AM_DIRECTORY env var as a simple JSON string mapping
    aad_object_id → email. Override in production with your real directory."""
    import json

    raw = os.environ.get("AAM_AM_DIRECTORY", "{}")
    try:
        directory = json.loads(raw)
    except json.JSONDecodeError:
        directory = {}
    return directory.get(aad_object_id)


class _AAMBot(ActivityHandler):
    """Captures ConversationReferences on install and on every inbound activity.
    Replies with a single onboarding message so installers know the bot is wired."""

    async def on_members_added_activity(
        self, members_added: list[ChannelAccount], turn_context: TurnContext
    ):
        for m in members_added:
            if m.id != turn_context.activity.recipient.id:
                # An AM was added — they just installed the bot
                await store_conversation_ref(
                    activity=turn_context.activity, am_email_resolver=_default_aad_resolver
                )
                await turn_context.send_activity(
                    "AAM Briefings is installed. You'll receive a daily ranked list "
                    "of accounts to action, with the reasoning behind each one. "
                    "Reply `done`, `snooze`, or `wrong` to give feedback."
                )

    async def on_message_activity(self, turn_context: TurnContext):
        await store_conversation_ref(
            activity=turn_context.activity, am_email_resolver=_default_aad_resolver
        )
        # We don't process commands here; that's the FastAPI feedback API.
        await turn_context.send_activity(
            "Use the in-message buttons to give feedback, or POST to "
            "/v1/feedback on the AAM API."
        )


def _adapter() -> BotFrameworkAdapter:
    settings = BotFrameworkAdapterSettings(
        app_id=os.environ.get("AAM_TEAMS_BOT_APP_ID") or "",
        app_password=os.environ.get("AAM_TEAMS_BOT_APP_PASSWORD") or "",
    )
    tenant = os.environ.get("AAM_TEAMS_BOT_TENANT_ID") or os.environ.get("B2B_M365_TENANT_ID")
    if tenant:
        settings.channel_auth_tenant = tenant
    return BotFrameworkAdapter(settings)


app = FastAPI(title="AAM Teams Bot endpoint", version="0.1.0")
_bot = _AAMBot()


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.post("/api/messages")
async def messages(req: Request) -> Response:
    if "application/json" not in req.headers.get("content-type", ""):
        raise HTTPException(415, "expected application/json")
    body = await req.json()
    activity = Activity().deserialize(body)
    auth_header = req.headers.get("authorization", "")

    response = await _adapter().process_activity(activity, auth_header, _bot.on_turn)
    if response:
        return Response(content=response.body, status_code=response.status, media_type="application/json")
    return Response(status_code=200)
