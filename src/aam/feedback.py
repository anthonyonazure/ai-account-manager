"""FastAPI endpoints for AM feedback on briefing items.

Verdicts ("done", "snooze", "wrong") are stored in am_feedback. In a future
version, "wrong" verdicts decrement the weight for that signal kind for that
AM, and "done" with a positive note increments it — closing the loop on
ranker quality."""

from __future__ import annotations

import structlog
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from aam.db import AmFeedback, session

log = structlog.get_logger()
app = FastAPI(title="AAM feedback API", version="0.1.0")


class FeedbackBody(BaseModel):
    briefing_id: str
    account_id: str
    am_email: str
    verdict: str  # "done" | "snooze" | "wrong"
    note: str | None = None


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}


@app.post("/v1/feedback")
async def submit_feedback(body: FeedbackBody) -> dict:
    if body.verdict not in {"done", "snooze", "wrong"}:
        raise HTTPException(
            400, f"verdict must be one of done/snooze/wrong, got {body.verdict!r}"
        )
    async with session() as s:
        s.add(
            AmFeedback(
                briefing_id=body.briefing_id,
                account_id=body.account_id,
                am_email=body.am_email,
                verdict=body.verdict,
                note=body.note,
            )
        )
    log.info("aam.feedback.recorded", **body.model_dump())
    return {"ok": True}
