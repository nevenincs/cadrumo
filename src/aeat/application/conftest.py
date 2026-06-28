"""Pytest fixtures shared across `application/` tests.

The autouse `_isolated_aeat_root` fixture redirects
`Settings.aeat_local_storage_root` to a function-scoped `tmp_path` for
unit tests under this package, so the active-profile pointer file that
`register_active_profile` / `select_profile` write via
`_write_active_profile_pointer` lands inside the test sandbox and
never bleeds into the project's real `var/storage/` directory.

Opt-in live tests are intentionally excluded. They need the operator's
real active-profile pointer and encrypted bucket so Cl@ve-backed reads
exercise the same state the CLI uses.

Isolation uses a scoped environment-variable context (not
`override_settings`) on purpose: `BaseSettings` re-reads variables on every
`Settings()` instantiation, so later nested fixtures that mutate
other AEAT_* variables compose correctly. An `override_settings`
context manager would snapshot the Settings at this fixture's
setup time and mask any subsequent env changes from the per-test
fixture chain.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest

from ..tests._env import temporary_env


@pytest.fixture(autouse=True, name="_isolated_aeat_root")
def isolated_aeat_root(request: pytest.FixtureRequest, tmp_path: Path) -> Iterator[None]:
    """Point `Settings.aeat_local_storage_root` at the test's `tmp_path`."""

    if request.node.get_closest_marker("aeat_live"):
        yield
        return
    with temporary_env(AEAT_LOCAL_STORAGE_ROOT=str(tmp_path)):
        yield
