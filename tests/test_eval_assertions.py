"""Tests for evals.assertions — AAM briefing quality rules."""

from __future__ import annotations

from evals.assertions import (
    briefing_has_actions_or_states_quiet,
    narrative_length_reasonable,
    narrative_mentions_top_account,
    no_banned_tropes,
    top_action_matches_highest_weighted_score,
)


def _state(actions=None, markdown=""):
    return {"actions": actions or [], "markdown": markdown}


def _action(name, weighted=0.5, signal_kind="ticket_velocity_risk", direction="risk"):
    return {
        "account": {"name": name, "tier": "gold", "arr": 100000, "industry": "fin"},
        "signal_kind": signal_kind,
        "signal_score": 0.9,
        "weighted_score": weighted,
        "direction": direction,
        "detail": {},
    }


def test_quiet_day_passes_without_actions():
    s = _state(actions=[], markdown="**Nothing to action today.** All your accounts steady.")
    ok, _ = briefing_has_actions_or_states_quiet(s)
    assert ok


def test_no_actions_no_acknowledgment_fails():
    s = _state(actions=[], markdown="some unrelated text")
    ok, _ = briefing_has_actions_or_states_quiet(s)
    assert not ok


def test_top_action_in_order_passes():
    s = _state(actions=[_action("A", 0.9), _action("B", 0.7)])
    ok, _ = top_action_matches_highest_weighted_score(s)
    assert ok


def test_top_action_out_of_order_fails():
    s = _state(actions=[_action("Lo", 0.4), _action("Hi", 0.95)])
    ok, _ = top_action_matches_highest_weighted_score(s)
    assert not ok


def test_narrative_mentions_top_account():
    s = _state(actions=[_action("Vanguard")], markdown="Top concern is Vanguard...")
    ok, _ = narrative_mentions_top_account(s)
    assert ok


def test_narrative_misses_top_account():
    s = _state(actions=[_action("Vanguard")], markdown="Generic text")
    ok, _ = narrative_mentions_top_account(s)
    assert not ok


def test_narrative_length_reasonable():
    s = _state(markdown="x " * 50)  # 50 words
    ok, _ = narrative_length_reasonable(s)
    assert ok


def test_narrative_too_short():
    s = _state(markdown="too short")
    ok, _ = narrative_length_reasonable(s)
    assert not ok


def test_no_banned_tropes_passes():
    s = _state(markdown="clean text with no buzzwords")
    ok, _ = no_banned_tropes(s)
    assert ok


def test_banned_tropes_caught():
    s = _state(markdown="we should leverage our synergy")
    ok, _ = no_banned_tropes(s)
    assert not ok
