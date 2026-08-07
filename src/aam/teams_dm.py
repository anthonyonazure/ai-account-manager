"""Microsoft Teams real DM delivery via Bot Framework (Path B).

How this works:
  1. The AAM bot is registered as an Azure Bot Service resource (Microsoft
     App ID + password) and exposed as a Teams app via a manifest.
  2. AMs install the bot from the Teams app catalog. On install, Teams sends
     a `conversationUpdate` event to our /api/messages endpoint with a full
     ConversationReference for that user.
  3. We persist the ConversationReference per AM email (looked up via
     User.PrincipalName / aadObjectId).
  4. To send a proactive DM later (this module), we restore the
     ConversationReference and call adapter.continue_conversation().

Without a stored ConversationReference for an AM, the bot cannot DM them —
they have to install the bot first. This is a Microsoft Teams security
requirement, not a code limitation.
"""

from __future__ import annotations

import os

import structlog
from botbuilder.core import (
    BotFrameworkAdapter,
    BotFrameworkAdapterSettings,
    TurnContext,
)
from botbuilder.schema import (
    Activity,
    ActivityTypes,
    Attachment,
    ChannelAccount,
    ConversationAccount,
    ConversationReference,
)
from sqlalchemy import select

from aam.db import TeamsConversationRef, session

log = structlog.get_logger()


def _adapter_settings() -> BotFrameworkAdapterSettings | None:
    app_id = os.environ.get("AAM_TEAMS_BOT_APP_ID")
    app_pw = os.environ.get("AAM_TEAMS_BOT_APP_PASSWORD")
    if not app_id or not app_pw:
        return None
    settings = BotFrameworkAdapterSettings(app_id=app_id, app_password=app_pw)
    # Single-tenant bots authenticate against the customer tenant, not
    # the default Bot Framework directory.
    tenant = os.environ.get("AAM_TEAMS_BOT_TENANT_ID") or os.environ.get(
        "B2B_M365_TENANT_ID"
    )
    if tenant:
        settings.channel_auth_tenant = tenant
    return settings


def _adapter() -> BotFrameworkAdapter | None:
    s = _adapter_settings()
    return BotFrameworkAdapter(s) if s else None


async def _load_ref(am_email: str) -> TeamsConversationRef | None:
    async with session() as s:
        return (
            await s.execute(
                select(TeamsConversationRef).where(
                    TeamsConversationRef.am_email == am_email
                )
            )
        ).scalar_one_or_none()


def _ref_to_botbuilder(row: TeamsConversationRef) -> ConversationReference:
    return ConversationReference(
        channel_id="msteams",
        service_url=row.service_url,
        conversation=ConversationAccount(
            id=row.conversation_id, tenant_id=row.tenant_id
        ),
        bot=ChannelAccount(id=row.bot_id, name=row.bot_name),
        user=ChannelAccount(
            id=row.user_id, name=row.user_name, aad_object_id=row.aad_object_id
        ),
    )


def _build_card_attachment(
    *, am_email: str, narrative: str, actions: list[dict]
) -> Attachment:
    """Reuse the AdaptiveCard schema from teams_channel.py."""
    from aam.teams_channel import _build_card

    msg = _build_card(am_email=am_email, narrative=narrative, actions=actions)
    return Attachment(
        content_type="application/vnd.microsoft.card.adaptive",
        content=msg["attachments"][0]["content"],
    )


async def send_proactive_dm(
    *, am_email: str, narrative: str, actions: list[dict]
) -> dict:
    adapter = _adapter()
    if not adapter:
        log.info("aam.teams_dm.skipped", reason="no_bot_credentials")
        return {"skipped": True, "reason": "no_bot_credentials"}

    ref_row = await _load_ref(am_email)
    if not ref_row:
        log.info("aam.teams_dm.skipped", reason="no_conversation_ref", am=am_email)
        return {"skipped": True, "reason": "no_conversation_ref_for_am"}

    ref = _ref_to_botbuilder(ref_row)

    async def _send(turn_context: TurnContext) -> None:
        attachment = _build_card_attachment(
            am_email=am_email, narrative=narrative, actions=actions
        )
        await turn_context.send_activity(
            Activity(type=ActivityTypes.message, attachments=[attachment])
        )

    bot_id = os.environ.get("AAM_TEAMS_BOT_APP_ID")
    try:
        await adapter.continue_conversation(ref, _send, bot_id=bot_id)
        log.info("aam.teams_dm.delivered", am=am_email)
        return {"ok": True}
    except Exception as e:
        log.exception("aam.teams_dm.delivery_failed", am=am_email, err=str(e)[:300])
        return {"ok": False, "error": str(e)[:300]}


# ---------- Capturing conversation references ----------


async def store_conversation_ref(*, activity: Activity, am_email_resolver) -> None:
    """Called from the bot's /api/messages handler whenever an inbound
    activity carries enough info to identify the AM. The resolver maps
    AAD object id → AM email (your AM directory lookup)."""
    user = activity.from_property
    if not user or not user.aad_object_id:
        log.info("teams_bot.skipped_capture", reason="no_aad_id")
        return
    am_email = await am_email_resolver(user.aad_object_id)
    if not am_email:
        log.info(
            "teams_bot.skipped_capture",
            reason="aad_not_in_am_directory",
            aad=user.aad_object_id,
        )
        return

    ref = TurnContext.get_conversation_reference(activity)
    # conversation/user/bot are all optional on the wire model. A reference
    # missing any of them cannot be used to open a proactive DM later, so
    # storing it would only defer the failure to send time.
    if ref.conversation is None or ref.user is None or ref.bot is None:
        log.warning(
            "teams_bot.skipped_capture", reason="incomplete_conversation_reference"
        )
        return
    conversation, user_account, bot_account = ref.conversation, ref.user, ref.bot
    service_url = ref.service_url or ""
    async with session() as s:
        existing = (
            await s.execute(
                select(TeamsConversationRef).where(
                    TeamsConversationRef.am_email == am_email
                )
            )
        ).scalar_one_or_none()
        if existing:
            existing.service_url = service_url
            existing.conversation_id = conversation.id
            existing.tenant_id = conversation.tenant_id or ""
            existing.user_id = user_account.id
            existing.user_name = user_account.name or ""
            existing.bot_id = bot_account.id
            existing.bot_name = bot_account.name or ""
            existing.aad_object_id = user.aad_object_id
        else:
            s.add(
                TeamsConversationRef(
                    am_email=am_email,
                    aad_object_id=user.aad_object_id,
                    service_url=service_url,
                    conversation_id=conversation.id,
                    tenant_id=conversation.tenant_id or "",
                    user_id=user_account.id,
                    user_name=user_account.name or "",
                    bot_id=bot_account.id,
                    bot_name=bot_account.name or "",
                )
            )
    log.info("teams_bot.captured_ref", am=am_email, conv=conversation.id)
