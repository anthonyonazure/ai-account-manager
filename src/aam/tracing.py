"""Optional Langfuse tracing — same pattern as partner-onboarding-agent.

Enabled when LANGFUSE_PUBLIC_KEY + LANGFUSE_SECRET_KEY are set, otherwise no-op.
"""

from __future__ import annotations

import os
from collections.abc import Callable
from typing import Any, Literal, TypeVar

F = TypeVar("F", bound=Callable[..., Any])

# The observation kinds Langfuse accepts. Spelling them out keeps a typo in a
# @traced(...) decorator a type error rather than a silent runtime rejection.
ObservationType = Literal[
    "generation",
    "embedding",
    "span",
    "agent",
    "tool",
    "chain",
    "retriever",
    "evaluator",
    "guardrail",
]


def _enabled() -> bool:
    return bool(
        os.environ.get("LANGFUSE_PUBLIC_KEY") and os.environ.get("LANGFUSE_SECRET_KEY")
    )


if _enabled():
    from langfuse import observe  # type: ignore[import-not-found]

    def traced(
        name: str | None = None, as_type: ObservationType | None = None
    ) -> Callable[[F], F]:
        def decorator(fn: F) -> F:
            return observe(name=name or fn.__name__, as_type=as_type)(fn)  # type: ignore[return-value]

        return decorator

    def flush() -> None:
        from langfuse import get_client

        get_client().flush()

else:

    def traced(
        name: str | None = None, as_type: ObservationType | None = None
    ) -> Callable[[F], F]:
        def decorator(fn: F) -> F:
            return fn

        return decorator

    def flush() -> None:
        return None
