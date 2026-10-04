"""A native profile worker persists a supervised ledger add for later reads."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest
from click.testing import Result

from ....adapters.persistence.storage.master_key.active_session import close_active_bucket_session
from ....tests.cli_envelope import unwrap_cli_result
from .cli_runner import invoke_cached_cli
from .runtime_profile_cli_fixture import (
    NativeCliProfileFixture,
    RuntimeFailureObservation,
    native_cli_profile_scope,
)

pytestmark = [
    pytest.mark.integration,
    pytest.mark.hex_entrypoint,
    pytest.mark.windows_only,
    pytest.mark.skipif(sys.platform != "win32", reason="requires native Windows profile workers"),
    pytest.mark.usefixtures("authority_operation"),
]

_PROFILE_FACTS = {
    "taxpayer_type.entity_type": "natural_person",
    "identity.name": "Native",
    "identity.surnames": "Add",
    "activities.description": "design",
    "censo.activity_start_date": "2025-01-01",
    "tax_residence.jurisdiction_scope": "common_regime",
    "iva.regime": "GENERAL",
    "iva.m303_regime_composition": "general",
    "iva.redeme_enrolled": "false",
    "iva.cash_accounting_regime_enrolled": "false",
    "iva.voluntary_sii_enrolled": "false",
    "iva.hydrocarbon_deposit_advance_payment_deduction_entitled": "false",
}


def _invoke(profile: NativeCliProfileFixture, *command: str) -> Result:
    assert profile.label is not None
    close_active_bucket_session()
    result = invoke_cached_cli(
        ("--language", "en", "--format", "json", "--profile", profile.label, "--profile-secrets-stdin", *command),
        input=json.dumps({"profile_passphrase": profile.passphrase}),
    )
    assert profile.passphrase not in result.output
    return result


def test_native_exact_profile_add_is_readable_after_session_reauthentication(tmp_path: Path) -> None:
    """Exercise the actual encrypted CLI worker, then read its committed row."""
    with native_cli_profile_scope(tmp_path) as profile:
        failures: list[RuntimeFailureObservation] = []
        profile.failure_observer = failures.append
        profile.register(label="native-ledger-add", facts=_PROFILE_FACTS)
        added = _invoke(
            profile,
            "app",
            "ledger",
            "add",
            "--date",
            "2026-04-15",
            "--amount",
            "23.00",
            "--direction",
            "OUTGOING",
            "--description",
            "native exact-profile add",
            "--idempotency-key",
            "native-exact-profile-add",
        )
        assert added.exit_code == 0, (added.output, failures)
        created = unwrap_cli_result(added)
        transaction_id = created["transaction_id"]
        assert isinstance(transaction_id, str) and len(transaction_id) == 64

        viewed = _invoke(profile, "app", "ledger", "view", transaction_id)
        assert viewed.exit_code == 0, viewed.output
        readback = unwrap_cli_result(viewed)
        assert readback["transaction_id"] == transaction_id
        assert readback["transaction"]["description"] == "native exact-profile add"


def test_native_add_and_list_refuse_an_unregistered_or_malformed_own_account(tmp_path: Path) -> None:
    """``--account`` names a register entry: an unregistered id refuses the add, a non-id refuses the list."""
    with native_cli_profile_scope(tmp_path) as profile:
        profile.register(label="native-ledger-account", facts=_PROFILE_FACTS)
        added = _invoke(
            profile,
            "app",
            "ledger",
            "add",
            "--date",
            "2026-04-15",
            "--amount",
            "23.00",
            "--direction",
            "OUTGOING",
            "--description",
            "bank fee",
            "--account",
            "acc-01",
        )
        malformed = _invoke(profile, "app", "ledger", "list", "--account", "ES9121000418450200051332")
        listed = _invoke(profile, "app", "ledger", "list", "--account", "acc-01")

    assert added.exit_code != 0
    assert "acc-01" in added.output
    assert malformed.exit_code != 0
    assert "ES9121000418450200051332" not in malformed.output
    assert listed.exit_code == 0, listed.output
    assert unwrap_cli_result(listed)["rows"] == []
