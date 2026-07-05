"""Real CLI tests for Modelo 145 local communication commands."""

from __future__ import annotations

import os
from collections.abc import Iterator
from pathlib import Path

import pytest

from ....tests.cli_runner import invoke_cached_cli
from ....tests.secure_sql import dev_test_database_password, isolated_runtime_profile
from .envelope_helpers import unwrap_schema_envelope

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_BUCKET_ID = "44444444-4444-4444-8444-444444444444"
_CREATE_ARGS = [
    "app",
    "modelo",
    "m145",
    "create",
    "--year",
    "2026",
    "--casilla",
    "perceptor.nif=12345678Z",
    "--casilla",
    "perceptor.primer-apellido=Garcia",
    "--casilla",
    "perceptor.segundo-apellido=Lopez",
    "--casilla",
    "perceptor.nombre=Ana",
    "--casilla",
    "perceptor.anio-nacimiento=1981",
]


@pytest.fixture
def isolated_m145_cli_backend(tmp_path: Path) -> Iterator[None]:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID) as runtime:
        env = {
            "AEAT_LOCAL_STORAGE_ROOT": str(runtime.storage_root),
            "AEAT_ACTIVE_PROFILE": runtime.bucket_id,
            "AEAT_SECRET_STORE_BACKEND": "file",
            "AEAT_SECRET_STORE_DIR": str(tmp_path / "secrets"),
            "AEAT_SECRET_PASSPHRASE": dev_test_database_password(runtime.settings),
            "AEAT_OUTPUT_LANGUAGE": "en",
        }
        old_env = {key: os.environ.get(key) for key in env}
        try:
            os.environ.update(env)
            yield
        finally:
            for key, value in old_env.items():
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value


def _invoke(args: list[str]):
    return invoke_cached_cli(args)


def _create_record_id() -> str:
    result = _invoke(["--format", "json", *_CREATE_ARGS])
    assert result.exit_code == 0, result.output
    payload = unwrap_schema_envelope(result.output)
    return payload["record"]["communication_record_id"]


def test_m145_group_registers_closed_action_verbs() -> None:
    result = _invoke(["app", "modelo", "m145", "--help"])

    assert result.exit_code == 0, result.output
    assert "create" in result.output
    assert "validate" in result.output
    assert "export" in result.output
    assert "mark-delivered-to-payer" in result.output
    assert "mark-locally-completed" in result.output


def test_m145_create_validate_export_and_transitions_delegate_to_real_service(
    isolated_m145_cli_backend: None,
) -> None:
    communication_record_id = _create_record_id()

    validation = _invoke(["--format", "json", "app", "modelo", "m145", "validate", communication_record_id[:12]])
    assert validation.exit_code == 0, validation.output
    validation_payload = unwrap_schema_envelope(validation.output)
    assert validation_payload["valid"] is True
    assert validation_payload["issue_count"] == 0

    exported = _invoke(["--format", "json", "app", "modelo", "m145", "export", communication_record_id[:12]])
    assert exported.exit_code == 0, exported.output
    export_payload = unwrap_schema_envelope(exported.output)
    assert export_payload["communication_record_id"] == communication_record_id
    assert export_payload["payload_sha256"]
    assert export_payload["payload_text"].startswith("<T145010>")

    delivered = _invoke(
        ["--format", "json", "app", "modelo", "m145", "mark-delivered-to-payer", communication_record_id[:12]],
    )
    assert delivered.exit_code == 0, delivered.output
    delivered_payload = unwrap_schema_envelope(delivered.output)
    assert delivered_payload["record"]["state"] == "delivered_to_payer"

    completed = _invoke(
        ["--format", "json", "app", "modelo", "m145", "mark-locally-completed", communication_record_id[:12]],
    )
    assert completed.exit_code == 0, completed.output
    completed_payload = unwrap_schema_envelope(completed.output)
    assert completed_payload["record"]["state"] == "locally_completed"


def test_m145_create_requires_casilla_input(isolated_m145_cli_backend: None) -> None:
    result = _invoke(["app", "modelo", "m145", "create", "--year", "2026"])

    assert result.exit_code != 0
    assert "--casilla" in result.output


def test_m145_help_avoids_filing_and_live_vocabulary() -> None:
    result = _invoke(["app", "modelo", "m145", "--help"])

    assert result.exit_code == 0, result.output
    forbidden = {"filing", "deadline", "live-read", "submit", "receipt"}
    lowered = result.output.lower()
    assert forbidden.isdisjoint(lowered.split())
