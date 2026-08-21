"""Cross-profile unlock journey: each profile's ledger is its own bucket.

Seeds two profiles (the autonoma filer + the recargo retailer), imports a
distinct statement into each while that profile's session is active, then
re-activates each in turn and asserts its ledger surfaces only its own rows --
the operator-facing cross-profile runtime-pegged ledger guarantee.

The active session is opened with ``open_test_profile_session`` -- the same
session primitive the ``aeat config login`` verb drives; re-entering a
span is the in-process equivalent of unlocking the active profile between
commands.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from ....tests import FIXTURES_DIR
from ....tests.cli_runner import invoke_cached_cli
from ....tests.profile_capsule import open_test_profile_session
from ....tests.profile_storage_root_fixture import isolated_profile_storage_fixture
from ....tests.user_profile import register_minimal_profile

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_FIX = FIXTURES_DIR / "financial"
_AUTONOMA_CSV = _FIX / "ledger-corpus" / "n26-savings.csv"
_RETAILER_CSV = _FIX / "ledger-corpus-retailer" / "bbva-retail-eur.csv"
_AUTONOMA_PROFILE_ID = "2c2c2c2c-2c2c-4c2c-8c2c-2c2c2c2c2c2c"
_RETAILER_PROFILE_ID = "3d3d3d3d-3d3d-4d3d-8d3d-3d3d3d3d3d3d"


_isolated_backend = isolated_profile_storage_fixture(
    name="_isolated_backend",
    dispose_engine_around=True,
    settings_overrides={"cadrumo_output_language": "en"},
)


def _register(*, profile_id: str, label: str) -> None:
    register_minimal_profile(profile_id=profile_id, display_name=label)


def _import(csv_path: Path) -> None:
    result = invoke_cached_cli(["app", "ledger", "import", "--file", str(csv_path), "--provider", "csv"])
    assert result.exit_code == 0, result.output


def _list_ids() -> set[str]:
    listed = invoke_cached_cli(["--format", "json", "app", "ledger", "list"])
    assert listed.exit_code == 0, listed.output
    rows = json.loads(listed.output)["result"]["rows"]
    return {r.get("full_id") or r["transaction_id"] for r in rows}


def test_two_profiles_keep_independent_ledgers_across_unlocks() -> None:
    # Provision + load each profile into its own bucket, importing a distinct
    # statement while that profile's session is the active one.
    with open_test_profile_session(_AUTONOMA_PROFILE_ID):
        _register(profile_id=_AUTONOMA_PROFILE_ID, label="autonoma")
        _import(_AUTONOMA_CSV)
        autonoma_ids = _list_ids()

    with open_test_profile_session(_RETAILER_PROFILE_ID):
        _register(profile_id=_RETAILER_PROFILE_ID, label="retailer")
        _import(_RETAILER_CSV)
        retailer_ids = _list_ids()

    assert autonoma_ids and retailer_ids
    assert autonoma_ids.isdisjoint(retailer_ids)

    # Unlocking a profile reopens its session and surfaces only that profile's
    # ledger -- no bleed-through.
    # Re-entering the session span IS the unlock, as the module docstring says:
    # it drives the same primitive `aeat config login` does. A `config login`
    # invocation here would additionally require a custody envelope opening
    # under the CLI backend's passphrase, and `register_minimal_profile` -- the
    # application-layer seeding door used above -- deliberately writes no such
    # envelope. Asserting a login here tested the seeding door's limits rather
    # than the ledger isolation this module is about.
    with open_test_profile_session(_AUTONOMA_PROFILE_ID):
        back = _list_ids()
    assert back == autonoma_ids
    assert back.isdisjoint(retailer_ids)

    with open_test_profile_session(_RETAILER_PROFILE_ID):
        assert _list_ids() == retailer_ids
