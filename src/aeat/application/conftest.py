"""Pytest fixtures shared across `application/` tests.

The autouse `_isolated_aeat_root` fixture redirects
`Settings.aeat_local_storage_root` to a function-scoped `tmp_path` for
every test under this package, so the active-profile pointer file that
`register_active_profile` / `select_profile` write via
`_write_active_profile_pointer` lands inside the test sandbox and
never bleeds into the project's real `var/storage/` directory.

Isolation flows through :func:`aeat.core.config.override_settings`,
the canonical injection mechanism — not raw `monkeypatch.setenv` —
so the test code path mirrors what production code does when it
needs to override settings (a context manager around a block).
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest

from aeat.core.config import override_settings


@pytest.fixture(autouse=True)
def _isolated_aeat_root(tmp_path: Path) -> Iterator[None]:
    """Redirect `Settings.aeat_local_storage_root` to the test's tmp_path."""

    with override_settings(aeat_local_storage_root=tmp_path):
        yield
