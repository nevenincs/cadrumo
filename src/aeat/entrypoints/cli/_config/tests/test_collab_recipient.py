"""Real-behavior CLI tests for ``aeat config collab recipient add/list/remove``.

Exercises the recipient-fingerprint registry CLI against a genuine encrypted
profile bucket (no mocks): register a recipient's X25519 public key, confirm
it lists with its derived fingerprint, confirm a duplicate id refuses, and
confirm removal drops it from the register. The registered public key is then
proven to be the exact key
``aeat app modelo review-package encrypt-for-recipient`` seals against in
:mod:`~aeat.entrypoints.cli.tests.test_modelo_review_package_recipient_encryption_verb`.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PrivateKey

from .....tests.cli_runner import invoke_typer_app
from .....tests.secure_sql import isolated_profile_storage_root
from ... import app as root_app
from ...tests.envelope_helpers import unwrap_schema_envelope as _payload

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]


def _create_profile(name: str = "collabco") -> None:
    create = invoke_typer_app(
        root_app,
        [
            "config",
            "profile",
            "create",
            name,
            "--quiet",
            "--tax-id",
            "12345678Z",
            "--entity-type",
            "natural_person",
            "--name",
            "Collab",
            "--surnames",
            "Operator",
            "--activity",
            "design",
            "--iva-regime",
            "GENERAL",
        ],
    )
    assert create.exit_code == 0, f"profile create failed: {create.output}"


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
                "kents-accountant",
                "--public-key",
                public_key_hex,
                "--label",
                "Kent's accountant",
            ],
        )
        assert add_result.exit_code == 0, add_result.output
        add_payload = _payload(add_result.output)
        assert add_payload["recipient_id"] == "kents-accountant"
        assert add_payload["label"] == "Kent's accountant"
        assert add_payload["public_key_hex"] == public_key_hex
        assert len(add_payload["fingerprint_sha256"]) == 64
        bytes.fromhex(add_payload["fingerprint_sha256"])  # is valid hex

        _dispose()
        list_result = invoke_typer_app(root_app, ["--format", "json", "config", "collab", "recipient", "list"])
        assert list_result.exit_code == 0, list_result.output
        list_payload = _payload(list_result.output)
        assert list_payload["count"] == 1
        assert list_payload["recipients"][0]["recipient_id"] == "kents-accountant"
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
                "kents-accountant",
                "--public-key",
                _fresh_public_key_hex(),
            ],
        )
        assert duplicate_result.exit_code != 0, duplicate_result.output

        _dispose()
        remove_result = invoke_typer_app(
            root_app,
            ["--format", "json", "config", "collab", "recipient", "remove", "kents-accountant"],
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


def test_collab_recipient_remove_unknown_id_refuses(tmp_path: Path) -> None:
    with isolated_profile_storage_root(tmp_path=tmp_path):
        _create_profile()
        _dispose()

        result = invoke_typer_app(root_app, ["config", "collab", "recipient", "remove", "no-such-recipient"])
        assert result.exit_code != 0, result.output
