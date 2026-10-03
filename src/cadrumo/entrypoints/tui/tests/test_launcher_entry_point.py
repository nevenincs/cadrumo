"""The installed module entry starts an empty-profile self-test and settles the shared authority."""

from __future__ import annotations

from pathlib import Path

import pytest

from ....domain.calculations.registry.authority import bundled_indexed_authority
from ....domain.calculations.registry.authority_store import AuthorityStoreError
from ....domain.calculations.registry.tests.shared_authority_isolation import isolated_shared_authority
from ..launcher import main, run_module

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


@pytest.mark.hex_entrypoint
def test_module_entry_composes_the_production_session_rather_than_refusing(
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
) -> None:
    """Bare execution composes the installed session; it no longer fails closed.

    The refusal this once asserted was the gap, not the contract: the module
    is how ``aeat app tui`` starts, so an entry that printed
    ``workbench.root.composition_required`` and exited meant the product had
    no reachable workbench at all. What remains fail-closed is narrower and
    still proven here: against an empty profile store the self-test completes
    without inventing a profile to serve.
    """
    from ....adapters.persistence.storage.tests.secure_sql import isolated_profile_storage_root

    with isolated_profile_storage_root(tmp_path=tmp_path):
        assert run_module(["--self-test"]) == 0

    assert "workbench.root.composition_required" not in capsys.readouterr().err


def test_an_orderly_exit_releases_the_shared_registry_authority(tmp_path: Path) -> None:
    """The shared owner holds its database open; the host lets go of it once the session ends in order."""
    from ....adapters.persistence.storage.tests.secure_sql import isolated_profile_storage_root

    authority_root = tmp_path / "authority"
    authority_root.mkdir()
    with isolated_shared_authority(authority_root) as database:
        opened = bundled_indexed_authority()
        with opened.operation():
            pass

        with isolated_profile_storage_root(tmp_path=tmp_path / "profiles"):
            assert run_module(["--self-test"]) == 0

        with pytest.raises(AuthorityStoreError, match="closed"), opened.operation():
            pass
        # Windows refuses to delete a file a live connection holds.
        database.unlink()


def test_a_session_that_fails_leaves_the_shared_registry_authority_to_its_error(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """A failure that escapes the session reaches the caller untouched and releases nothing."""
    from .. import installed_session

    def failing_session(*, headless: bool, auto_pilot: object) -> int:
        raise RuntimeError("session unavailable")

    monkeypatch.setattr(installed_session, "run_installed_workbench_session", failing_session)
    with isolated_shared_authority(tmp_path):
        opened = bundled_indexed_authority()
        with pytest.raises(RuntimeError, match="session unavailable"):
            main(headless=True)

        with opened.operation() as operation:
            assert operation.pin().logical_generation
