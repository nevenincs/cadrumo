"""The installed module entry starts an empty-profile self-test."""

from __future__ import annotations

from pathlib import Path

import pytest

from ..launcher import run_module

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
