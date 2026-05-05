# ai-account-manager (Project 2 — design stub)

Always-on revenue co-pilot. Watches every active partner account across HubSpot, Zendesk, Planner, SharePoint, and the internal portal. Each morning, hands every human account manager a ranked list: who to call, what to upsell, who's silently churning, who's ready for tier promotion, where co-sell openings exist.

> **Status**: design only. Implementation begins after Project 1 is shipped to the demo bar.

## Architecture (planned)

```
                        ┌── HubSpot ──┐
                        ├── Zendesk ──┤
  cron + event triggers ┼── M365 ─────┼──► snapshot pullers ──► AccountSnapshot table (Postgres)
                        ├── Portal ───┤                                 │
                        └─────────────┘                                 ▼
                                                       deterministic signal computers
                                                                       │
                                                                       ▼
                                                          composite scoring (no LLM)
                                                       ┌────────────────┴───────────────┐
                                                       ▼                                ▼
                                          ranker (per AM, per day)         briefing agent (LLM)
                                                                                       │
                                                                ┌──────────────────────┼─────────────┐
                                                                ▼                      ▼             ▼
                                                          morning email           Slack DM     web dashboard
                                                                                       │
                                                                                       ▼
                                                                            feedback loop (snooze/done/dismiss)
                                                                                       │
                                                                                       ▼
                                                                              re-trains the ranker
```

## Signals to compute

| Signal | Source | Direction |
|---|---|---|
| Engagement decay | HubSpot activity Δ over rolling 30/60/90 | high = risk |
| Ticket velocity & sentiment | Zendesk ticket volume, P1 count, CSAT | high P1 / low CSAT = risk |
| Module gap | Portal usage vs services purchased | unused modules = expansion blocker |
| Usage growth | Portal logins, active modules trend | upward = upsell opportunity |
| Renewal proximity | HubSpot contract end date | <90 days = priority |
| Doc activity | SharePoint access logs | low = disengagement |
| Co-sell fit | Tier × industry × portfolio overlap | partner-of-partner intros |

## Build order

1. Reuse all of `b2b-agent-toolkit` adapters (already exists).
2. Add Postgres schema: `account_snapshots`, `signal_history`, `briefings`, `am_feedback`.
3. Nightly puller (APScheduler or RQ) per source.
4. Deterministic signal computers — straight Python, no LLM (math should never be hallucinated).
5. Ranker — weighted score, weights tuned via AM feedback.
6. LangGraph briefing agent — one run per AM, generates ranked action list with reasoning + suggested talking points.
7. Output channels — email (M365), Slack DM, FastAPI dashboard.
8. Feedback loop endpoints — snooze / done / wrong, used to retrain weights.

## Estimate

4–5 weeks for portfolio-grade build. 10–12 weeks production-wired.
