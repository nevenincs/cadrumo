"""Cross-profile unlock journey: each profile's ledger is its own bucket.

Seeds two profiles (the Marta autonoma + the recargo retailer), imports a
distinct statement into each while that profile's session is active, then
re-activates each in turn and asserts its ledger surfaces only its own rows --
the operator-facing cross-profile runtime-pegged ledger guarantee.

The active session is opened with ``profile_create_storage_span`` -- the same
session primitive the ``aeat config switch`` verb drives; re-entering a
span is the in-process equivalent of unlocking the active profile between
commands.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path

import pytest

from ....adapters.persistence.storage.sql.engine import dispose_engine
from ....application.user_profile._orchestration import profile_create_storage_span
from ....application.user_profile._testing import register_minimal_profile
from ....application.workflow._persistence import workflow_state_repository
from ....core.config import override_settings
from ....tests import FIXTURES_DIR
from ....tests.cli_runner import invoke_cached_cli
from ....tests.secure_sql import isolated_profile_storage_root

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_FIX = FIXTURES_DIR / "financial"
_MARTA_CSV = _FIX / "ledger-corpus" / "n26-savings.csv"
_RETAILER_CSV = _FIX / "ledger-corpus-retailer" / "bbva-retail-eur.csv"


@pytest.fixture(autouse=True)
def _isolated_backend(tmp_path: Path) -> Iterator[None]:
    dispose_engine()
    with (
        override_settings(aeat_local_storage_root=tmp_path, aeat_output_language="en"),
        isolated_profile_storage_root(tmp_path=tmp_path),
    ):
        try:
            yield
        finally:
            dispose_engine()


def _register(name: str) -> None:
    workflow_state_repository().update(
        lambda state: register_minimal_profile(state, profile_id=name, enforce_unique_tax_id=False),
    )


def _import(csv_path: Path) -> None:
    result = invoke_cached_cli(["app", "ledger", "import", str(csv_path), "--provider", "csv"])
    assert result.exit_code == 0, result.output


def _list_ids() -> set[str]:
    listed = invoke_cached_cli(["--format", "json", "app", "ledger", "list"])
    assert listed.exit_code == 0, listed.output
    rows = json.loads(listed.output)["result"]["rows"]
    return {r.get("full_id") or r["transaction_id"] for r in rows}


def test_two_profiles_keep_independent_ledgers_across_unlocks() -> None:
    # Provision + load each profile into its own bucket, importing a distinct
    # statement while that profile's session is the active one.
    with profile_create_storage_span("marta"):
        _register("marta")
        _import(_MARTA_CSV)
        marta_ids = _list_ids()

    with profile_create_storage_span("retailer"):
        _register("retailer")
        _import(_RETAILER_CSV)
        retailer_ids = _list_ids()

    assert marta_ids and retailer_ids
    assert marta_ids.isdisjoint(retailer_ids)

    # Unlocking a profile reopens its session and surfaces only that profile's
    # ledger -- no bleed-through.
    with profile_create_storage_span("marta"):
        unlocked = invoke_cached_cli(["config", "switch", "marta"])
        assert unlocked.exit_code == 0, unlocked.output
        back = _list_ids()
    assert back == marta_ids
    assert back.isdisjoint(retailer_ids)

    with profile_create_storage_span("retailer"):
        assert _list_ids() == retailer_ids
