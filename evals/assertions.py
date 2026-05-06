"""Deterministic assertions over a generated AAM briefing.

Each assertion takes (briefing_state: dict) and returns
(passed: bool, detail: str). State is the final LangGraph state from
generate_briefing(am_email)."""

from __future__ import annotations

import re

# Same trope list as the marketing agent — these are universal red flags.
BANNED_TROPES = [
    "synergy", "leverage", "elevate", "unlock", "best-in-class",
    "world-class", "trusted advisor", "circle back", "low-hanging fruit",
    "move the needle", "thought leadership", "win-win",
]


def briefing_has_actions_or_states_quiet(state: dict) -> tuple[bool, str]:
    actions = state.get("actions") or []
    md = (state.get("markdown") or "").lower()
    if actions:
        return True, f"{len(actions)} actions present"
    if "no priority actions" in md or "nothing to action" in md or "all your accounts" in md:
        return True, "explicitly states quiet day"
    return False, "no actions and no quiet-day acknowledgment"


def top_action_matches_highest_weighted_score(state: dict) -> tuple[bool, str]:
    actions = state.get("actions") or []
    if not actions:
        return True, "no actions to order (vacuously true)"
    top = max(actions, key=lambda a: a["weighted_score"])
    if actions[0]["weighted_score"] == top["weighted_score"]:
        return True, "first action has highest weighted score"
    return False, (
        f"first action weighted={actions[0]['weighted_score']} "
        f"but max in list is {top['weighted_score']}"
    )


def narrative_mentions_top_account(state: dict) -> tuple[bool, str]:
    actions = state.get("actions") or []
    narrative = (state.get("markdown") or "")
    if not actions:
        return True, "no actions; nothing to mention"
    top_name = actions[0]["account"]["name"]
    return top_name in narrative, f"top account {top_name!r} {'in' if top_name in narrative else 'NOT in'} markdown"


def at_least_one_specific_number(state: dict) -> tuple[bool, str]:
    """Each action's 'Why:' line should include a concrete number — count, %,
    days, dollars, etc. Numbers are a stronger signal than narratives."""
    md = state.get("markdown") or ""
    why_lines = re.findall(r"Why:.*?(?=\n\d+\. |$)", md, flags=re.S)
    has_num = sum(1 for line in why_lines if re.search(r"\d", line))
    n = len(why_lines)
    if n == 0:
        return True, "no Why lines (vacuously true)"
    return has_num == n, f"{has_num}/{n} Why-lines contain a number"


def no_banned_tropes(state: dict) -> tuple[bool, str]:
    md = (state.get("markdown") or "").lower()
    hits = [t for t in BANNED_TROPES if t in md]
    return len(hits) == 0, f"tropes found: {hits}" if hits else "no tropes"


def narrative_length_reasonable(state: dict) -> tuple[bool, str]:
    md = state.get("markdown") or ""
    # First non-header text block ≈ the narrative
    blocks = [b.strip() for b in md.split("\n\n") if b.strip() and not b.strip().startswith("#")]
    narrative = next((b for b in blocks if not b.startswith("##") and not b.startswith("_")), "")
    words = len(narrative.split())
    return 10 <= words <= 200, f"narrative is {words} words (want 10-200)"


ALL_ASSERTIONS = [
    briefing_has_actions_or_states_quiet,
    top_action_matches_highest_weighted_score,
    narrative_mentions_top_account,
    at_least_one_specific_number,
    no_banned_tropes,
    narrative_length_reasonable,
]


def evaluate_briefing(state: dict, am_email: str) -> dict:
    results = []
    for fn in ALL_ASSERTIONS:
        passed, detail = fn(state)
        results.append({"assertion": fn.__name__, "passed": passed, "detail": detail})
    return {
        "am_email": am_email,
        "action_count": len(state.get("actions") or []),
        "passed": all(r["passed"] for r in results),
        "results": results,
    }
