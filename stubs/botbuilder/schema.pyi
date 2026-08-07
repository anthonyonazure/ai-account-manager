"""Minimal typing stub for the botbuilder-schema names this project imports.

See the note in core.pyi: the package ships no py.typed marker. These are the
Bot Framework wire models AAM constructs directly.
"""

from typing import Any

class ActivityTypes:
    message: str
    conversation_update: str

class ChannelAccount:
    id: str
    name: str | None
    aad_object_id: str | None
    def __init__(
        self,
        id: str = ...,
        name: str | None = ...,
        aad_object_id: str | None = ...,
        **kwargs: Any,
    ) -> None: ...

class ConversationAccount:
    id: str
    tenant_id: str | None
    conversation_type: str | None
    def __init__(
        self,
        id: str = ...,
        tenant_id: str | None = ...,
        conversation_type: str | None = ...,
        is_group: bool | None = ...,
        name: str | None = ...,
        **kwargs: Any,
    ) -> None: ...

class Attachment:
    def __init__(
        self,
        content_type: str = ...,
        content: Any = ...,
        content_url: str | None = ...,
        name: str | None = ...,
        **kwargs: Any,
    ) -> None: ...

class Activity:
    type: str
    text: str | None
    attachments: list[Attachment] | None
    service_url: str | None
    channel_id: str | None
    conversation: ConversationAccount | None
    from_property: ChannelAccount | None
    recipient: ChannelAccount | None
    def __init__(
        self,
        type: str = ...,
        text: str | None = ...,
        attachments: list[Attachment] | None = ...,
        **kwargs: Any,
    ) -> None: ...
    def deserialize(self, data: dict[str, Any]) -> Activity: ...

class ConversationReference:
    activity_id: str | None
    user: ChannelAccount | None
    bot: ChannelAccount | None
    conversation: ConversationAccount | None
    channel_id: str | None
    locale: str | None
    service_url: str | None
    def __init__(
        self,
        activity_id: str | None = ...,
        user: ChannelAccount | None = ...,
        bot: ChannelAccount | None = ...,
        conversation: ConversationAccount | None = ...,
        channel_id: str | None = ...,
        service_url: str | None = ...,
        locale: str | None = ...,
        **kwargs: Any,
    ) -> None: ...
