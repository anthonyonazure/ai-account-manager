"""Minimal typing stub for the botbuilder-core names this project imports.

botbuilder-core ships no py.typed marker and has no stub package on PyPI, so
mypy would otherwise treat the whole Bot Framework boundary as untyped. Only
the classes and members AAM actually calls are declared here; extend this file
as usage grows rather than widening the module to Any.
"""

from collections.abc import Awaitable, Callable
from typing import Any

from botbuilder.schema import Activity, ChannelAccount, ConversationReference

class TurnContext:
    activity: Activity
    async def send_activity(self, activity: Activity | str) -> Any: ...
    @staticmethod
    def get_conversation_reference(activity: Activity) -> ConversationReference: ...

class BotFrameworkAdapterSettings:
    app_id: str
    app_password: str | None
    channel_auth_tenant: str | None
    oauth_endpoint: str | None
    open_id_metadata: str | None
    def __init__(
        self,
        app_id: str,
        app_password: str | None = ...,
        channel_auth_tenant: str | None = ...,
        oauth_endpoint: str | None = ...,
        open_id_metadata: str | None = ...,
        **kwargs: Any,
    ) -> None: ...

class BotFrameworkAdapter:
    def __init__(self, settings: BotFrameworkAdapterSettings) -> None: ...
    async def process_activity(
        self,
        activity: Activity,
        auth_header: str,
        logic: Callable[[TurnContext], Awaitable[Any]],
    ) -> Any: ...
    async def continue_conversation(
        self,
        reference: ConversationReference,
        callback: Callable[[TurnContext], Awaitable[Any]],
        bot_id: str | None = ...,
        claims_identity: Any | None = ...,
        audience: str | None = ...,
    ) -> None: ...

class ActivityHandler:
    async def on_turn(self, turn_context: TurnContext) -> None: ...
    async def on_message_activity(self, turn_context: TurnContext) -> None: ...
    async def on_members_added_activity(
        self, members_added: list[ChannelAccount], turn_context: TurnContext
    ) -> None: ...
