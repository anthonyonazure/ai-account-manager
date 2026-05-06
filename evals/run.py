"""AAM eval harness.

Generates a briefing for each of the 3 seeded AMs, scores against the
deterministic assertions, writes a markdown + JSON report.

Run with stub LLM (no API key) for a fast deterministic baseline, or with
ANTHROPIC_API_KEY set to score the real model on briefing quality."""

from __future__ import annotations

import asyncio
import json
import os
import uuid
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from aam.briefing import generate_briefing
from aam.scoring import score_all
from aam.seed import seed as seed_db

from evals.assertions import evaluate_briefing

EVAL_DIR = Path(__file__).resolve().parent
RESULTS_DIR = EVAL_DIR / "results"
SAMPLE_AMS = ["alice@cyberco.com", "bob@cyberco.com", "carmen@cyberco.com"]


async def run_eval(*, ams: list[str] | None = None) -> dict:
    ams = ams or SAMPLE_AMS

    # Re-seed + score so the eval is reproducible regardless of prior state
    db_path = Path(os.environ.get("AAM_DATABASE_URL", "sqlite+aiosqlite:///./aam.db").replace("sqlite+aiosqlite:///", ""))
    if db_path.exists():
        db_path.unlink()
    await seed_db()
    await score_all()

    scored = []
    for am in ams:
        state = await generate_briefing(am)
        scored.append(evaluate_briefing(state, am))

    pass_count = sum(1 for s in scored if s["passed"])
    failures_by_assertion = Counter()
    for s in scored:
        for r in s["results"]:
            if not r["passed"]:
                failures_by_assertion[r["assertion"]] += 1

    return {
        "run_id": uuid.uuid4().hex[:10],
        "ran_at": datetime.now(timezone.utc).isoformat(),
        "am_count": len(ams),
        "pass_count": pass_count,
        "fail_count": len(ams) - pass_count,
        "pass_rate_pct": round(pass_count / max(len(ams), 1) * 100, 1),
        "model": "stub" if not os.environ.get("ANTHROPIC_API_KEY") else os.environ.get("AAM_MODEL", "claude-sonnet-4-6"),
        "failures_by_assertion": dict(failures_by_assertion),
        "per_am": scored,
    }


def write_reports(report: dict) -> tuple[Path, Path]:
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    rid = report["run_id"]
    json_path = RESULTS_DIR / f"{rid}.json"
    md_path = RESULTS_DIR / f"{rid}.md"

    json_path.write_text(json.dumps(report, indent=2, default=str))

    lines = [
        f"# AAM eval run `{rid}`",
        "",
        f"- **Ran:** {report['ran_at']}",
        f"- **Model:** `{report['model']}`",
        f"- **Pass rate:** {report['pass_rate_pct']}% ({report['pass_count']} / {report['am_count']})",
        "",
        "## Failures by assertion",
        "",
        "| Assertion | Failures |",
        "|---|---|",
    ]
    for name, n in sorted(report["failures_by_assertion"].items(), key=lambda x: -x[1]):
        lines.append(f"| `{name}` | {n} |")
    if not report["failures_by_assertion"]:
        lines.append("| _no failures_ | 0 |")

    lines += ["", "## Per-AM detail", "", "| AM | Actions | Passed |", "|---|---|---|"]
    for s in report["per_am"]:
        mark = "✓" if s["passed"] else "✗"
        lines.append(f"| {s['am_email']} | {s['action_count']} | {mark} |")

    md_path.write_text("\n".join(lines))
    return json_path, md_path


async def main() -> dict:
    report = await run_eval()
    json_path, md_path = write_reports(report)
    print(f"Pass rate: {report['pass_rate_pct']}%  ({report['pass_count']}/{report['am_count']})")
    print(f"Reports:  {md_path}  +  {json_path}")
    return report


if __name__ == "__main__":
    asyncio.run(main())
