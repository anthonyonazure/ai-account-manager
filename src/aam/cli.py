"""Typer CLI for AAM."""

from __future__ import annotations

import asyncio
from pathlib import Path

import structlog
import typer
from dotenv import load_dotenv
from rich.console import Console

# Load .env early so AAM_*, ANTHROPIC_API_KEY, B2B_* are visible to all modules.
load_dotenv()

from aam.briefing import generate_briefing
from aam.db import init_db
from aam.pullers import pull_all_accounts
from aam.scoring import score_all
from aam.seed import seed as seed_db
from aam.tracing import flush as flush_traces

app = typer.Typer(no_args_is_help=True, add_completion=False)
console = Console()
log = structlog.get_logger()


@app.command()
def seed():
    """Wipe-and-seed the local SQLite DB with 12 synthetic partner accounts."""
    db = Path("aam.db")
    if db.exists():
        db.unlink()
        console.print("[dim]Removed existing aam.db[/]")
    asyncio.run(seed_db())
    console.print("[green]Seeded 12 accounts and their snapshots.[/]")


@app.command()
def init():
    """Create empty DB schema (no seed data)."""
    asyncio.run(init_db())
    console.print("[green]DB initialized.[/]")


@app.command()
def pull():
    """Refresh snapshots from live (or mocked) sources for every account."""
    n = asyncio.run(pull_all_accounts())
    console.print(f"[green]Pulled snapshots for {n} accounts.[/]")


@app.command()
def score():
    """Compute every signal for every account from the latest snapshot."""
    n = asyncio.run(score_all())
    console.print(f"[green]Computed and persisted {n} signals.[/]")


@app.command()
def brief(
    am: str = typer.Option(..., "--am", help="AM email (e.g. alice@cyberco.com)"),
    save: bool = typer.Option(True, help="Save briefing markdown to briefings/"),
):
    """Generate today's briefing for an AM."""
    final = asyncio.run(generate_briefing(am))
    md = final.get("markdown", "")
    console.print(md)
    if save:
        out = Path("briefings") / f"{am.replace('@', '_at_')}-{_today()}.md"
        out.parent.mkdir(exist_ok=True)
        out.write_text(md)
        console.print(f"\n[dim]Saved: {out}[/]")
    flush_traces()


@app.command()
def feedback_server(host: str = "0.0.0.0", port: int = 8002):
    """Run the FastAPI feedback endpoints."""
    import uvicorn

    uvicorn.run("aam.feedback:app", host=host, port=port, reload=False)


@app.command()
def teams_bot(host: str = "0.0.0.0", port: int = 3978):
    """Run the Bot Framework /api/messages endpoint (Path B Teams DM channel).

    Public URL must be set as the bot's messaging endpoint in Azure Bot Service.
    Use ngrok / cloudflared during development, e.g. `ngrok http 3978`.
    """
    import uvicorn

    uvicorn.run("aam.teams_bot_server:app", host=host, port=port, reload=False)


def _today() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


if __name__ == "__main__":
    app()
