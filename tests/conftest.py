"""Shared fixtures: seed an isolated SQLite DB per session."""

from __future__ import annotations

import asyncio
import os
import tempfile
from pathlib import Path

import pytest

# Ensure stub LLM path
os.environ.pop("ANTHROPIC_API_KEY", None)


@pytest.fixture(scope="session")
def seeded_db():
    tmp = Path(tempfile.mkdtemp()) / "aam_test.db"
    os.environ["AAM_DATABASE_URL"] = f"sqlite+aiosqlite:///{tmp}"

    # Re-import after env var is set so the module-level engine binds correctly
    import importlib

    import aam.db

    importlib.reload(aam.db)

    # seed.py imports from aam.db — also reload it
    import aam.seed

    importlib.reload(aam.seed)

    asyncio.run(aam.seed.seed())
    yield tmp
    tmp.unlink(missing_ok=True)
