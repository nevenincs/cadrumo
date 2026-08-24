"""Real-behavior CLI tests for ``aeat config collab recipient add/list/remove``.

Exercises the recipient-fingerprint registry CLI against a genuine encrypted
profile bucket (no mocks): register a recipient's X25519 public key, confirm
it lists with its derived fingerprint, confirm a duplicate id refuses, and
confirm removal drops it from the register. The registered public key is then
proven to be the exact key
``aeat app modelo review-package encrypt-for-recipient`` seals against in
:mod:`~entrypoints.cli.tests.test_modelo_review_package_recipient_encryption_verb`.

See Also:
    :mod:`~entrypoints.cli._config._collab`
        Command handlers for the ``config collab recipient`` surface.
    :class:`~application.modelo.RecipientFingerprintRegistryRepository`
        Encrypted active-bucket registry the CLI delegates to.
    :class:`~application.modelo.RecipientFingerprintRecord`
        Public-key trust record projected by ``add`` and ``list``.
    :func:`~application.modelo.public_key_hex_from_raw_bytes`
        Application validator for raw X25519 public-key bytes.
    :class:`~entrypoints.cli._config._collab_payloads.ConfigCollabRecipientAddResult`
        JSON result schema asserted after ``recipient add``.
    :class:`~entrypoints.cli._config._collab_payloads.ConfigCollabRecipientListResult`
        JSON result schema asserted after ``recipient list``.
    :class:`~entrypoints.cli._config._collab_payloads.ConfigCollabRecipientRemoveResult`
        JSON result schema asserted after ``recipient remove``.
    :func:`~tests.cli_runner.invoke_typer_app`
        Real Typer runner used to exercise the config root.
    :func:`~tests.secure_sql.isolated_profile_storage_root`
        Encrypted profile-storage harness used by these integration tests.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PrivateKey
from pydantic import ValidationError

from .....tests.cli_envelope import unwrap_schema_envelope as _payload
from .....tests.cli_runner import invoke_typer_app
from .....tests.secure_sql import isolated_profile_storage_root
from .....tests.user_profile import register_cli_profile
from ... import app as root_app

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]


def _create_profile(name: str = "collabco") -> None:
    """Register the profile through the shared CLI registration door."""
    register_cli_profile(
        label=name,
        facts={
            "identity.tax_id": "12345678Z",
            "taxpayer_type.entity_type": "natural_person",
            "identity.name": "Collab",
            "identity.surnames": "Operator",
            "activities.description": "design",
            "iva.regime": "GENERAL",
            "tax_residence.jurisdiction_scope": "common_regime",
            "iva.m303_regime_composition": "general",
            "iva.redeme_enrolled": "false",
            "iva.cash_accounting_regime_enrolled": "false",
            "iva.voluntary_sii_enrolled": "false",
            "iva.hydrocarbon_deposit_advance_payment_deduction_entitled": "false",
        },
    )


def _dispose() -> None:
    from .....adapters.persistence.storage.sql.engine import dispose_engine

    dispose_engine()


def _fresh_public_key_hex() -> str:
    return X25519PrivateKey.generate().public_key().public_bytes_raw().hex()


def test_collab_recipient_add_then_list_then_remove(tmp_path: Path) -> None:
    with isolated_profile_storage_root(tmp_path=tmp_path):
        _create_profile()
        _dispose()

        public_key_hex = _fresh_public_key_hex()
        add_result = invoke_typer_app(
            root_app,
            [
                "--format",
                "json",
                "config",
                "collab",
                "recipient",
                "add",
                "my-accountant",
                "--public-key",
                public_key_hex,
                "--label",
                "My accountant",
            ],
        )
        assert add_result.exit_code == 0, add_result.output
        add_payload = _payload(add_result.output)
        assert add_payload["recipient_id"] == "my-accountant"
        assert add_payload["label"] == "My accountant"
        assert add_payload["public_key_hex"] == public_key_hex
        assert len(add_payload["fingerprint_sha256"]) == 64
        bytes.fromhex(add_payload["fingerprint_sha256"])  # is valid hex

        _dispose()
        list_result = invoke_typer_app(root_app, ["--format", "json", "config", "collab", "recipient", "list"])
        assert list_result.exit_code == 0, list_result.output
        list_payload = _payload(list_result.output)
        assert list_payload["count"] == 1
        assert list_payload["recipients"][0]["recipient_id"] == "my-accountant"
        assert list_payload["recipients"][0]["public_key_hex"] == public_key_hex

        # A duplicate recipient_id refuses instructively rather than silently
        # clobbering the registered fingerprint.
        _dispose()
        duplicate_result = invoke_typer_app(
            root_app,
            [
                "config",
                "collab",
                "recipient",
                "add",
                "my-accountant",
                "--public-key",
                _fresh_public_key_hex(),
            ],
        )
        assert duplicate_result.exit_code != 0, duplicate_result.output

        _dispose()
        remove_result = invoke_typer_app(
            root_app,
            ["--format", "json", "config", "collab", "recipient", "remove", "my-accountant"],
        )
        assert remove_result.exit_code == 0, remove_result.output
        remove_payload = _payload(remove_result.output)
        assert remove_payload["remaining"] == 0

        _dispose()
        list_after_remove = invoke_typer_app(root_app, ["--format", "json", "config", "collab", "recipient", "list"])
        assert list_after_remove.exit_code == 0, list_after_remove.output
        assert _payload(list_after_remove.output)["count"] == 0


def test_collab_recipient_add_rejects_malformed_public_key(tmp_path: Path) -> None:
    with isolated_profile_storage_root(tmp_path=tmp_path):
        _create_profile()
        _dispose()

        result = invoke_typer_app(
            root_app,
            ["config", "collab", "recipient", "add", "someone", "--public-key", "not-hex"],
        )
        assert result.exit_code != 0, result.output


def test_recipient_payload_refuses_an_arbitrary_fingerprint() -> None:
    """The displayed trust fingerprint is always derived from the registered key."""

    from datetime import UTC, datetime

    from .._collab_payloads import RecipientFingerprintRowPayload

    with pytest.raises(ValidationError, match="fingerprint_sha256"):
        RecipientFingerprintRowPayload(
            recipient_id="my-accountant",
            label="My accountant",
            public_key_hex=_fresh_public_key_hex(),
            fingerprint_sha256="0" * 64,
            added_at=datetime(2026, 8, 1, tzinfo=UTC),
        )


def test_collab_recipient_remove_unknown_id_refuses(tmp_path: Path) -> None:
    with isolated_profile_storage_root(tmp_path=tmp_path):
        _create_profile()
        _dispose()

        result = invoke_typer_app(root_app, ["config", "collab", "recipient", "remove", "no-such-recipient"])
        assert result.exit_code != 0, result.output
