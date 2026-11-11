"""A native profile worker persists a supervised ledger add for later reads."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from cadrumo.tests.cli_envelope import unwrap_cli_result
from cadrumo_runtime.host.tests.native_commands.runtime_profile_cli_fixture import (
    RuntimeFailureObservation,
    native_cli_profile_scope,
)

from ...native_profile_facts import native_general_iva_facts
from .profile_cli_support import invoke_native_profile

pytestmark = [
    pytest.mark.integration,
    pytest.mark.hex_entrypoint,
    pytest.mark.windows_only,
    pytest.mark.skipif(sys.platform != "win32", reason="requires native Windows profile workers"),
    pytest.mark.usefixtures("authority_operation"),
]

_PROFILE_FACTS = native_general_iva_facts()


def test_native_exact_profile_add_is_readable_after_session_reauthentication(tmp_path: Path) -> None:
    """Exercise the actual encrypted CLI worker, then read its committed row."""
    with native_cli_profile_scope(tmp_path) as profile:
        failures: list[RuntimeFailureObservation] = []
        profile.failure_observer = failures.append
        profile.register(label="native-ledger-add", facts=_PROFILE_FACTS)
        added = invoke_native_profile(
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

        viewed = invoke_native_profile(profile, "app", "ledger", "view", transaction_id)
        assert viewed.exit_code == 0, viewed.output
        readback = unwrap_cli_result(viewed)
        assert readback["transaction_id"] == transaction_id
        assert readback["transaction"]["description"] == "native exact-profile add"


def test_native_add_and_list_refuse_an_unregistered_or_malformed_own_account(tmp_path: Path) -> None:
    """``--account`` names a register entry: an unregistered id refuses the add, a non-id refuses the list."""
    with native_cli_profile_scope(tmp_path) as profile:
        profile.register(label="native-ledger-account", facts=_PROFILE_FACTS)
        added = invoke_native_profile(
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
        malformed = invoke_native_profile(profile, "app", "ledger", "list", "--account", "ES9121000418450200051332")
        listed = invoke_native_profile(profile, "app", "ledger", "list", "--account", "acc-01")

    assert added.exit_code != 0
    assert "acc-01" in added.output
    assert malformed.exit_code != 0
    assert "ES9121000418450200051332" not in malformed.output
    assert listed.exit_code == 0, listed.output
    assert unwrap_cli_result(listed)["rows"] == []
