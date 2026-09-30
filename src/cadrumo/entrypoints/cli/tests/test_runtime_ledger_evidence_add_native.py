"""A native exact-profile worker commits encrypted invoice evidence once per key."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest
from click.testing import Result

from ....adapters.persistence.storage.master_key.active_session import close_active_bucket_session
from ....tests.cli_envelope import unwrap_cli_result
from ._runtime_profile_cli_fixture import (
    NativeCliProfileFixture,
    RuntimeFailureObservation,
    native_cli_profile_scope,
)
from .cli_runner import invoke_cached_cli

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
    "identity.surnames": "Evidence",
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


def test_native_exact_profile_evidence_add_replay_and_readback(tmp_path: Path) -> None:
    """Prove installed worker custody, keyed replay, and later exact-profile read."""
    invoice = tmp_path / "native-invoice.pdf"
    invoice.write_bytes(b"%PDF-1.4\n1 0 obj<</Type/Catalog>>endobj\ntrailer<</Root 1 0 R>>\n%%EOF\n")
    with native_cli_profile_scope(tmp_path) as profile:
        failures: list[RuntimeFailureObservation] = []
        profile.failure_observer = failures.append
        profile.register(label="native-ledger-evidence-add", facts=_PROFILE_FACTS)
        command = (
            "app",
            "ledger",
            "evidence",
            "add",
            str(invoice),
            "--supplier",
            "Synthetic Supplier",
            "--idempotency-key",
            "native-evidence-add-once",
        )

        first = _invoke(profile, *command)
        assert first.exit_code == 0, (first.output, failures)
        created = unwrap_cli_result(first)
        evidence_id = created["evidence_id"]
        assert isinstance(evidence_id, str) and len(evidence_id) == 16
        assert len(created["bucket_event_ids"]) == 1

        replay = _invoke(profile, *command)
        assert replay.exit_code == 0, (replay.output, failures)
        repeated = unwrap_cli_result(replay)
        assert repeated["evidence_id"] == evidence_id
        assert repeated["bucket_event_ids"] == []

        viewed = _invoke(profile, "app", "ledger", "evidence", "view", evidence_id)
        assert viewed.exit_code == 0, (viewed.output, failures)
        readback = unwrap_cli_result(viewed)
        assert readback["evidence_id"] == evidence_id
        assert readback["supplier"] == "Synthetic Supplier"
