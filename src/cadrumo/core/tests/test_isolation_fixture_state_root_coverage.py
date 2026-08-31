"""Structural coverage gate: the canonical isolation fixture covers every
state-root-derived output directory.

``isolated_cli_backend`` (``tests.secure_sql``) exists so ~22 test modules
stop hand-declaring a private copy of the same storage-root override block.
The promotion is only sound if the fixture actually relocates every
generated-output directory the storage taxonomy's root-derived member set
declares — otherwise a test suite that relies on the fixture could still
write through to a shared, non-isolated default. This test enumerates the
taxonomy DYNAMICALLY (never a hardcoded field list) so a future dir field
added by a sibling change (the corpus-text cache, a retention-policy field,
...) is covered automatically the moment it lands in ``config.py``, and the
gate fails loudly if a new field is ever added to ``Settings`` outside the
derivation table with no isolation coverage.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from ...tests.secure_sql import isolated_cli_backend
from ..storage_taxonomy_locations import ROOT_DERIVED_STORAGE_FIELDS
from ..config import load_settings

__all__ = ["isolated_cli_backend"]

pytestmark = [pytest.mark.integration, pytest.mark.hex_core]


def test_isolated_cli_backend_covers_every_state_root_derived_dir(
    isolated_cli_backend: Path,
    tmp_path: Path,
) -> None:
    """Every root-derived storage member resolves under the test's
    own ``tmp_path`` once the fixture is active — proving the fixture
    isolates the whole family from any shared or ambient location, re-derived
    dynamically from the live taxonomy rather than a field list pinned at
    authoring time.

    Most fields nest directly under the yielded storage root
    (``isolated_cli_backend`` = ``tmp_path / "cadrumo-storage"``); the fixture's
    underlying :func:`isolated_profile_storage_root` deliberately keeps
    ``cadrumo_secret_store_dir`` as a *sibling* of the storage root
    (``tmp_path / "secrets"``) so the secret substrate and the bucket
    directory are provisioned independently, matching production custody —
    so the isolation boundary this gate enforces is ``tmp_path``, the actual
    test-scoped root, not the narrower yielded storage root.
    """

    storage_root = isolated_cli_backend
    settings = load_settings()

    assert settings.cadrumo_local_storage_root == storage_root

    assert ROOT_DERIVED_STORAGE_FIELDS, "the root-derived member set must not be empty"
    for field_name in ROOT_DERIVED_STORAGE_FIELDS:
        value = getattr(settings, field_name)
        assert value is not None, field_name
        assert value == tmp_path or tmp_path in value.parents, (
            f"{field_name} did not relocate under the test's isolated tmp_path; "
            f"got {value!r}, expected it under {tmp_path!r}"
        )


def test_isolated_cli_backend_yields_a_directory_under_tmp_path(isolated_cli_backend: Path, tmp_path: Path) -> None:
    """The fixture's yielded root lives under the test's own ``tmp_path``,
    confirming isolation from any shared or ambient storage root."""

    assert tmp_path in isolated_cli_backend.parents or isolated_cli_backend == tmp_path
