"""Each password-custodied profile exposes only its own ledger through the native worker."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from cadrumo.adapters.persistence.profile.tests.profile_registration import register_cli_profile
from cadrumo.adapters.persistence.storage.master_key.active_session import close_active_bucket_session
from cadrumo.adapters.persistence.storage.tests.secure_sql import isolated_profile_storage_root
from cadrumo.core.config import override_settings
from cadrumo.tests.inventory import FIXTURES_DIR
from cadrumo_runtime.host.tests.native_commands.runtime_profile_cli_fixture import native_cli_profile_server

from .profile_password_cli import invoke_with_profile_password

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint, pytest.mark.windows_only]

_FIX = FIXTURES_DIR / "financial"
_AUTONOMA_CSV = _FIX / "ledger-corpus" / "n26-savings.csv"
_RETAILER_CSV = _FIX / "ledger-corpus-retailer" / "bbva-retail-eur.csv"


def _register(label: str) -> None:
    register_cli_profile(
        label=label,
        facts={
            "taxpayer_type.entity_type": "natural_person",
            "identity.name": "Ledger",
            "identity.surnames": label,
            "activities.description": "design",
            "tax_residence.jurisdiction_scope": "common_regime",
            "iva.regime": "GENERAL",
            "iva.m303_regime_composition": "general",
            "iva.redeme_enrolled": "false",
            "iva.cash_accounting_regime_enrolled": "false",
            "iva.voluntary_sii_enrolled": "false",
            "iva.hydrocarbon_deposit_advance_payment_deduction_entitled": "false",
        },
        log_in=False,
    )
    close_active_bucket_session()


def _import(csv_path: Path, *, label: str) -> None:
    result = invoke_with_profile_password(
        ["app", "ledger", "import", "--file", str(csv_path), "--provider", "csv"], label=label
    )
    assert result.exit_code == 0, result.output


def _list_ids(*, label: str) -> set[str]:
    listed = invoke_with_profile_password(["--format", "json", "app", "ledger", "list"], label=label)
    assert listed.exit_code == 0, listed.output
    rows = json.loads(listed.output)["result"]["rows"]
    return {row.get("full_id") or row["transaction_id"] for row in rows}


def test_two_profiles_keep_independent_ledgers_across_unlocks(tmp_path: Path) -> None:
    with (
        isolated_profile_storage_root(tmp_path=tmp_path) as root,
        override_settings(cadrumo_output_language="en", cadrumo_cli_reveal_identifiers=True),
        native_cli_profile_server(root),
    ):
        _register("autonoma")
        _import(_AUTONOMA_CSV, label="autonoma")
        autonoma_ids = _list_ids(label="autonoma")
        _register("retailer")
        _import(_RETAILER_CSV, label="retailer")
        retailer_ids = _list_ids(label="retailer")
        assert autonoma_ids and retailer_ids
        assert autonoma_ids.isdisjoint(retailer_ids)

        # Every read supplies fresh password proof to the selected profile's
        # real worker; the parent holds no substitute bucket session.
        close_active_bucket_session()
        back = _list_ids(label="autonoma")
        assert back == autonoma_ids
        assert back.isdisjoint(retailer_ids)
        close_active_bucket_session()
        assert _list_ids(label="retailer") == retailer_ids
