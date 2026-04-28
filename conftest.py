"""Repo-root pytest conftest.

Two responsibilities, both hostable from the repo root so items
gathered under ``src/aeat/...`` (Rust-style colocated tests) pass
through the same enforcement surface as items under ``tests/``:

1. Auto-load ``env/.env`` into ``os.environ`` at module-load time so
   the ``AEAT_LIVE_TESTS_ENABLED`` gate in ``tests/conftest.py`` sees
   the same value the rest of the project's pydantic-settings stack
   reads. Without this, populating ``env/.env`` and running
   ``just test-live`` silently skips every ``live_read`` test because
   pytest never sources dotenv files itself.
2. Apply the nine-marker collection hook so any item carrying
   ``live_write`` (or missing the access/domain markers) is dropped /
   raised on. The hook body lives in :mod:`tests._marker_hook`; this
   conftest is a thin wrapper.

See ``tests/README.md`` and charter ``#116`` for the full taxonomy.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from tests._env_loader import load_env_file
from tests._marker_hook import apply as _apply_marker_contract

_REPO_ROOT = Path(__file__).resolve().parent
_ENV_FILE = _REPO_ROOT / "env" / ".env"


# Only the pytest collection-time gates need ``os.environ`` to mirror
# ``env/.env``. Application code reads its own settings via
# pydantic-settings (which sources ``env/.env`` directly), and tests
# that intentionally test "no-credentials" paths construct Settings
# subclasses with ``env_file=None``. Auto-promoting the full env file
# would silently break those isolation contracts.
_PYTEST_GATE_KEYS: frozenset[str] = frozenset(
    {
        "AEAT_LIVE_TESTS_ENABLED",
        "AEAT_LIVE_TESTS_GOOGLE",
    }
)


def _populate_env_from_dotenv() -> None:
    """Mirror the live-test gate keys from ``env/.env`` into ``os.environ``.

    Process-environment values always win — we never overwrite an
    existing key. The set is deliberately narrow (see
    :data:`_PYTEST_GATE_KEYS`); broader auto-promotion would defeat
    the ``IsolatedSettings(env_file=None)`` contract the MCP launcher
    tests rely on. Application code reads ``env/.env`` directly via
    pydantic-settings.
    """
    if not _ENV_FILE.exists():
        return
    pairs = load_env_file(_ENV_FILE)
    for key, value in pairs.items():
        if key in _PYTEST_GATE_KEYS:
            os.environ.setdefault(key, value)


_populate_env_from_dotenv()


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    """Delegate to the shared marker-contract enforcer."""
    _apply_marker_contract(config, items)
