"""Native profile-worker proof for registered collaboration-recipient operations."""

from __future__ import annotations

import json
import sys
from collections.abc import Mapping
from hashlib import sha256
from pathlib import Path

import pytest
from click.testing import Result
from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PrivateKey

from ....adapters.persistence.storage.master_key.active_session import close_active_bucket_session
from ....tests.cli_envelope import require_error_document, unwrap_cli_result
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
    "identity.surnames": "Collaboration",
    "activities.description": "design",
    "censo.activity_start_date": "2025-01-01",
    "contact.postcode": "28013",
    "tax_residence.jurisdiction_scope": "common_regime",
    "iva.regime": "GENERAL",
    "iva.m303_regime_composition": "general",
    "iva.redeme_enrolled": "false",
    "iva.cash_accounting_regime_enrolled": "false",
    "iva.voluntary_sii_enrolled": "false",
    "iva.hydrocarbon_deposit_advance_payment_deduction_entitled": "false",
}


def _invoke(
    profile: NativeCliProfileFixture,
    *command: str,
    env: Mapping[str, str | None] | None = None,
) -> Result:
    assert profile.label is not None
    close_active_bucket_session()
    result = invoke_cached_cli(
        (
            "--language",
            "en",
            "--format",
            "json",
            "--profile",
            profile.label,
            "--profile-secrets-stdin",
            *command,
        ),
        input=json.dumps({"profile_passphrase": profile.passphrase}),
        env=env,
    )
    assert profile.passphrase not in result.output
    return result


def _public_key_hex() -> str:
    return X25519PrivateKey.generate().public_key().public_bytes_raw().hex()


def _assert_registered_refusal(result: Result, *, code: str) -> None:
    assert result.exit_code != 0, result.output
    error = require_error_document(result.output)["error"]
    context = error["context"]
    assert context["refusal_code"] == code
    assert context["terminal_condition"] == "refused"
    assert context["effect"] == "none"
    operation_id = context["operation_id"]
    assert isinstance(operation_id, str) and len(operation_id) == 64


def test_native_three_operation_recipient_lifecycle_and_refusal_readback(tmp_path: Path) -> None:
    """One authenticated worker profile preserves public DTOs and audit history."""
    with native_cli_profile_scope(tmp_path) as profile:
        failures: list[RuntimeFailureObservation] = []
        profile.failure_observer = failures.append
        profile.register(label="native-collab-recipient", facts=_PROFILE_FACTS)

        zulu_key = _public_key_hex()
        zulu_added = _invoke(
            profile,
            "config",
            "collab",
            "recipient",
            "add",
            "zulu-accountant",
            "--public-key",
            zulu_key.upper(),
            "--label",
            "Zulu adviser",
        )
        assert zulu_added.exit_code == 0, (zulu_added.output, failures)
        zulu = unwrap_cli_result(zulu_added)
        assert zulu == {
            "recipient_id": "zulu-accountant",
            "label": "Zulu adviser",
            "public_key_hex": zulu_key,
            "fingerprint_sha256": sha256(bytes.fromhex(zulu_key)).hexdigest(),
            "added_at": zulu["added_at"],
        }
        assert isinstance(zulu["added_at"], str) and zulu["added_at"]

        alpha_key = _public_key_hex()
        alpha_added = _invoke(
            profile,
            "config",
            "collab",
            "recipient",
            "add",
            "alpha-accountant",
            "--public-key",
            alpha_key,
            "--label",
            "Alpha adviser",
        )
        assert alpha_added.exit_code == 0, (alpha_added.output, failures)
        alpha = unwrap_cli_result(alpha_added)
        assert alpha["recipient_id"] == "alpha-accountant"
        assert alpha["public_key_hex"] == alpha_key
        assert alpha["label"] == "Alpha adviser"
        assert alpha["fingerprint_sha256"] == sha256(bytes.fromhex(alpha_key)).hexdigest()
        assert isinstance(alpha["added_at"], str) and alpha["added_at"]

        listed = _invoke(profile, "config", "collab", "recipient", "list")
        assert listed.exit_code == 0, (listed.output, failures)
        before = unwrap_cli_result(listed)
        assert before["count"] == 2
        assert [row["recipient_id"] for row in before["recipients"]] == [
            "alpha-accountant",
            "zulu-accountant",
        ]
        assert before["recipients"] == [alpha, zulu]

        duplicate = _invoke(
            profile,
            "config",
            "collab",
            "recipient",
            "add",
            "zulu-accountant",
            "--public-key",
            _public_key_hex(),
        )
        _assert_registered_refusal(duplicate, code="REFUSED_MODELO_RECIPIENT_ALREADY_REGISTERED")

        malformed = _invoke(
            profile,
            "config",
            "collab",
            "recipient",
            "add",
            "malformed-key",
            "--public-key",
            "not-hex",
        )
        assert malformed.exit_code != 0, malformed.output
        assert "not-hex" not in malformed.output

        removed = _invoke(
            profile,
            "config",
            "collab",
            "recipient",
            "remove",
            "alpha-accountant",
        )
        assert removed.exit_code == 0, (removed.output, failures)
        removal = unwrap_cli_result(removed)
        assert removal == {"recipient_id": "alpha-accountant", "remaining": 1}

        missing = _invoke(
            profile,
            "config",
            "collab",
            "recipient",
            "remove",
            "missing-accountant",
        )
        _assert_registered_refusal(missing, code="REFUSED_MODELO_RECIPIENT_NOT_REGISTERED")

        listed_after = _invoke(profile, "config", "collab", "recipient", "list")
        assert listed_after.exit_code == 0, (listed_after.output, failures)
        after = unwrap_cli_result(listed_after)
        assert after["count"] == 1
        assert after["recipients"] == [zulu]

        registered_history = _invoke(
            profile,
            "config",
            "profile",
            "history",
            "--event-type",
            "collab_event.recipient.registered",
        )
        assert registered_history.exit_code == 0, (registered_history.output, failures)
        registrations = unwrap_cli_result(registered_history)["events"]
        assert len(registrations) == 2
        registration_payloads = {event["object_id"]: event["payload"] for event in registrations}
        assert registration_payloads == {
            "alpha-accountant": {
                "recipient_id": "alpha-accountant",
                "label": "Alpha adviser",
                "fingerprint_sha256": alpha["fingerprint_sha256"],
            },
            "zulu-accountant": {
                "recipient_id": "zulu-accountant",
                "label": "Zulu adviser",
                "fingerprint_sha256": zulu["fingerprint_sha256"],
            },
        }
        assert all("public_key_hex" not in payload for payload in registration_payloads.values())

        removed_history = _invoke(
            profile,
            "config",
            "profile",
            "history",
            "--event-type",
            "collab_event.recipient.removed",
        )
        assert removed_history.exit_code == 0, (removed_history.output, failures)
        removal_events = unwrap_cli_result(removed_history)["events"]
        assert len(removal_events) == 1
        assert removal_events[0]["object_id"] == "alpha-accountant"
        assert removal_events[0]["payload"] == {"recipient_id": "alpha-accountant"}

        returned_definitions = {
            item.definition_id
            for item in failures
            if item.stage == "profile_operation_returned" and item.definition_id is not None
        }
        assert returned_definitions >= {
            "config.collab.recipient.add",
            "config.collab.recipient.list",
            "config.collab.recipient.remove",
        }
