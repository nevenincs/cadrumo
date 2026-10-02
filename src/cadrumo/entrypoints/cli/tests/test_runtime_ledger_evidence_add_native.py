"""A native exact-profile worker commits encrypted invoice evidence once per key."""

from __future__ import annotations

import json
import sys
from hashlib import sha256
from pathlib import Path

import pytest
from click.testing import Result

from ....adapters.persistence.storage.attachment import AttachmentStore
from ....adapters.persistence.storage.master_key.active_session import (
    close_active_bucket_session,
    current_active_bucket_session,
)
from ....application.user_profile.login_session import login_profile, resolve_login_target
from ....core.redaction.rules import redact_structured_for_cli_output
from ....domain.calculations.registry.authority import PinnedAuthorityOperation
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


def test_native_exact_profile_evidence_add_replay_and_readback(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    authority_operation: PinnedAuthorityOperation,
) -> None:
    """Retain caller-relative bytes through native add, keyed replay and read."""
    caller = tmp_path / "caller"
    (caller / "invoices").mkdir(parents=True)
    source_path = "invoices/native-invoice.pdf"
    invoice = caller / source_path
    invoice_bytes = b"%PDF-1.4\n1 0 obj<</Type/Catalog>>endobj\ntrailer<</Root 1 0 R>>\n%%EOF\n"
    invoice.write_bytes(invoice_bytes)
    expected_digest = sha256(invoice_bytes).hexdigest()
    monkeypatch.chdir(caller)
    with native_cli_profile_scope(tmp_path) as profile:
        assert caller != profile.storage_root
        assert not (profile.storage_root / source_path).exists()
        failures: list[RuntimeFailureObservation] = []
        profile.failure_observer = failures.append
        profile.register(label="native-ledger-evidence-add", facts=_PROFILE_FACTS)
        assert profile.label is not None
        bucket_id = resolve_login_target(profile.label).bucket_id
        expected_cli_bucket_id = redact_structured_for_cli_output({"bucket_id": bucket_id}, reveal_identifiers=False)[
            "bucket_id"
        ]
        command = (
            "app",
            "ledger",
            "evidence",
            "add",
            source_path,
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
        assert created["source_path"] == source_path
        assert created["source_sha256"] == created["attachment_id"] == expected_digest
        assert len(created["bucket_event_ids"]) == 1

        replay = _invoke(profile, *command)
        assert replay.exit_code == 0, (replay.output, failures)
        repeated = unwrap_cli_result(replay)
        assert repeated["evidence_id"] == evidence_id
        assert repeated["source_path"] == source_path
        assert repeated["source_sha256"] == repeated["attachment_id"] == expected_digest
        assert repeated["bucket_event_ids"] == []

        invoice.unlink()
        viewed = _invoke(profile, "app", "ledger", "evidence", "view", evidence_id)
        assert viewed.exit_code == 0, (viewed.output, failures)
        readback = unwrap_cli_result(viewed)
        assert readback["bucket_id"] == expected_cli_bucket_id
        assert readback["evidence_id"] == evidence_id
        assert readback["supplier"] == "Synthetic Supplier"
        assert readback["source_path"] == source_path
        assert readback["source_sha256"] == readback["attachment_id"] == expected_digest

        # The input is gone and every CLI call has retired its worker session.
        # Reauthenticate independently to read the encrypted retained bytes.
        close_active_bucket_session()
        try:
            login = login_profile(
                name=profile.label,
                passphrase_callback=lambda: profile.passphrase,
                profile_decode_context=authority_operation.profile_decode_context(),
            )
            session = current_active_bucket_session()
            assert login.bucket_id == bucket_id
            assert session is not None and session.bucket_id == bucket_id
            store = AttachmentStore(bucket_id=bucket_id)
            assert store.load_manifest(expected_digest).bucket_id == bucket_id
            assert store.read_bytes(expected_digest) == invoice_bytes
        finally:
            close_active_bucket_session()
