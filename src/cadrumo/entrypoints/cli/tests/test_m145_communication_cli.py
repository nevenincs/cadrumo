"""Real CLI tests for Modelo 145 local communication commands.

See Also:
    :mod:`~entrypoints.cli._modelo_m145_cli`
        Thin Typer command registration under test.
    :mod:`~entrypoints.cli._modelo_m145_parsing`
        Parser boundary used before backend delegation.
    :mod:`~entrypoints.cli._modelo_m145_rendering`
        Rendering boundary used after backend delegation.
    :class:`~application.modelo.M145CommunicationRecordState`
        Backend state enum asserted after command transitions.
    :func:`~application.modelo.read_m145_communication_record`
        Backend read path used to verify real command effects.
    :mod:`~tests.cli_envelope`
        Schema-envelope helper used to inspect CLI JSON output.

The ``"secrets"`` literal in ``isolated_m145_cli_backend`` below is not an
arbitrary injected value: it must agree with what
:func:`~tests.secure_sql.isolated_runtime_profile` already minted the master
key under, since that fixture derives ``cadrumo_secret_store_dir`` from the
real taxonomy accessor. The CLI subprocesses this env drives must
independently compute the same location to unlock the profile the fixture
already created; renaming it to a fictional segment breaks that handoff.
"""

from __future__ import annotations

import os
import re
from collections.abc import Iterator
from pathlib import Path
from typing import Final

import pytest

from ....application.modelo.m145_communication_records import (
    M145CommunicationRecordState,
    read_m145_communication_record,
)
from ....core.type_adapters import STR_KEYED_MAPPING_ADAPTER
from ....tests.cli_envelope import unwrap_schema_envelope
from ....tests.cli_runner import invoke_cached_cli
from ....tests.secure_sql import dev_test_database_password, isolated_runtime_profile

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

PINNED_TAXONOMY_LITERALS: Final[frozenset[str]] = frozenset({"secrets"})
"""Taxonomy-vocabulary literals this module deliberately pins. See the module docstring."""

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
_M145_HELP_SURFACES = [
    ("group", ["app", "modelo", "m145", "--help"]),
    ("create", ["app", "modelo", "m145", "create", "--help"]),
    ("validate", ["app", "modelo", "m145", "validate", "--help"]),
    ("export", ["app", "modelo", "m145", "export", "--help"]),
    ("mark-delivered-to-payer", ["app", "modelo", "m145", "mark-delivered-to-payer", "--help"]),
    ("mark-locally-completed", ["app", "modelo", "m145", "mark-locally-completed", "--help"]),
]
_FORBIDDEN_COMMAND_SURFACES = (
    "aeat-electronic-tramite",
    "deadline",
    "file",
    "filing",
    "live-read",
    "portal",
    "receipt",
    "submit",
    "tramite",
)
_FORBIDDEN_COMPATIBILITY_COMMAND_ALIASES = (
    "complete",
    "completed",
    "deliver",
    "deliver-to-payer",
    "delivered-to-payer",
    "locally-complete",
    "mark-complete",
    "mark-completed",
    "mark-delivered",
    "mark-locally-complete",
)
_FORBIDDEN_HELP_WORDS = frozenset(
    {
        "deadline",
        "file",
        "filed",
        "filing",
        "live-read",
        "live_read",
        "portal",
        "presentacion",
        "presentación",
        "presentar",
        "receipt",
        "shim",
        "submit",
        "submission",
        "tramite",
        "trámite",
    },
)
_FORBIDDEN_HELP_PHRASES = (
    "cadrumo electronic",
    "cadrumo submission",
    "compatibility alias",
    "deprecated spelling",
    "electronic tramite",
    "electronic trámite",
    "fake support",
    "live filing",
    "live submission",
    "portal read",
    "portal write",
    "send to aeat",
    "submit to aeat",
)


@pytest.fixture
def isolated_m145_cli_backend(tmp_path: Path) -> Iterator[str]:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID) as runtime:
        env = {
            "CADRUMO_LOCAL_STORAGE_ROOT": str(runtime.storage_root),
            "CADRUMO_ACTIVE_PROFILE": runtime.bucket_id,
            "CADRUMO_SECRET_STORE_BACKEND": "auto",
            "CADRUMO_SECRET_STORE_DIR": str(tmp_path / "secrets"),
            "CADRUMO_SECRET_PASSPHRASE": dev_test_database_password(runtime.settings),
            "CADRUMO_OUTPUT_LANGUAGE": "en",
        }
        old_env = {key: os.environ.get(key) for key in env}
        try:
            os.environ.update(env)
            yield runtime.bucket_id
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
    payload = STR_KEYED_MAPPING_ADAPTER.validate_python(unwrap_schema_envelope(result.output))
    record = STR_KEYED_MAPPING_ADAPTER.validate_python(payload["record"])
    communication_record_id = record["communication_record_id"]
    assert isinstance(communication_record_id, str)
    return communication_record_id


def _unwrap_error_envelope(output: str) -> dict[str, object]:
    payload = STR_KEYED_MAPPING_ADAPTER.validate_json(output)
    assert payload["status"] == "error"
    # The error spine now names the failing command (byte-identical to the
    # command= its success envelope emits); null only before a command resolves.
    assert isinstance(payload["command"], str) and payload["command"], payload["command"]
    assert payload["notices"] == []
    return STR_KEYED_MAPPING_ADAPTER.validate_python(payload["error"])


def _help_words(output: str) -> set[str]:
    return set(re.findall(r"[a-z0-9_]+(?:-[a-z0-9_]+)?", output.casefold()))


def test_m145_group_registers_closed_action_verbs() -> None:
    result = _invoke(["app", "modelo", "m145", "--help"])

    assert result.exit_code == 0, result.output
    assert "create" in result.output
    assert "validate" in result.output
    assert "export" in result.output
    assert "mark-delivered-to-payer" in result.output
    assert "mark-locally-completed" in result.output


def test_m145_create_validate_export_and_transitions_delegate_to_real_service(
    isolated_m145_cli_backend: str,
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
    persisted = read_m145_communication_record(communication_record_id[:12], bucket_id=isolated_m145_cli_backend)
    assert persisted.state is M145CommunicationRecordState.LOCALLY_COMPLETED
    assert persisted.delivered_to_payer_at is not None
    assert persisted.locally_completed_at is not None


def test_m145_create_requires_casilla_input(isolated_m145_cli_backend: None) -> None:
    result = _invoke(["app", "modelo", "m145", "create", "--year", "2026"])

    assert result.exit_code != 0
    assert "--casilla" in result.output


def test_m145_missing_record_failure_uses_central_error_boundary(isolated_m145_cli_backend: None) -> None:
    result = _invoke(["--format", "json", "app", "modelo", "m145", "validate", "0" * 12])

    assert result.exit_code == 1, result.output
    assert "Traceback" not in result.output
    error = _unwrap_error_envelope(result.output)
    assert error["code"] == "ERROR_M145_COMMUNICATION_RECORD_NOT_FOUND"
    assert error["category"] == "ERROR"
    assert error["context"] == {"communication_record_id": "000000000000"}


def test_m145_transition_failure_uses_central_error_boundary(isolated_m145_cli_backend: None) -> None:
    communication_record_id = _create_record_id()

    result = _invoke(
        ["--format", "json", "app", "modelo", "m145", "mark-locally-completed", communication_record_id[:12]],
    )

    assert result.exit_code == 2, result.output
    assert "Traceback" not in result.output
    error = _unwrap_error_envelope(result.output)
    assert error["code"] == "REFUSED_M145_COMMUNICATION_RECORD_TRANSITION"
    assert error["category"] == "REFUSED"
    assert error["context"] == {
        "communication_record_id": communication_record_id,
        "state": "created",
    }


@pytest.mark.parametrize("surface", _FORBIDDEN_COMMAND_SURFACES)
def test_m145_cli_rejects_forbidden_filing_like_command_surfaces(surface: str) -> None:
    result = _invoke(["app", "modelo", "m145", surface, "--help"])

    assert result.exit_code != 0, result.output
    assert "No such command" in result.output


@pytest.mark.parametrize("alias", _FORBIDDEN_COMPATIBILITY_COMMAND_ALIASES)
def test_m145_cli_rejects_compatibility_alias_command_spellings(alias: str) -> None:
    result = _invoke(["app", "modelo", "m145", alias, "--help"])

    assert result.exit_code != 0, result.output
    assert "No such command" in result.output


@pytest.mark.parametrize(("surface", "args"), _M145_HELP_SURFACES)
def test_m145_help_surfaces_avoid_filing_and_submission_vocabulary(surface: str, args: list[str]) -> None:
    result = _invoke(args)

    assert result.exit_code == 0, f"{surface} help failed:\n{result.output}"
    words = _help_words(result.output)
    forbidden_words = sorted(_FORBIDDEN_HELP_WORDS & words)
    lowered = result.output.casefold()
    forbidden_phrases = sorted(phrase for phrase in _FORBIDDEN_HELP_PHRASES if phrase in lowered)
    assert not forbidden_words, f"{surface} help contains forbidden words: {forbidden_words}\n{result.output}"
    assert not forbidden_phrases, f"{surface} help contains forbidden phrases: {forbidden_phrases}\n{result.output}"
