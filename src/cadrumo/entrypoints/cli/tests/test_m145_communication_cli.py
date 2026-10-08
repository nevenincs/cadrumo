"""Real CLI tests for Modelo 145 local communication commands.

See Also:
    :mod:`~entrypoints.cli._modelo_m145_cli`
        Thin Typer command registration under test.
    :mod:`~entrypoints.cli.tests.runtime_profile_cli_fixture`
        Authenticated profile and retained native worker fixture for behavior tests.
    :mod:`~entrypoints.cli._modelo_m145_parsing`
        Parser boundary used before backend delegation.
    :mod:`~entrypoints.cli._modelo_m145_rendering`
        Rendering boundary used after backend delegation.
    :mod:`~tests.cli_envelope`
        Schema-envelope helper used to inspect CLI JSON output.

Private command behavior tests use the authenticated profile and native worker
fixture. Public help and command-surface assertions remain platform-independent.
"""

from __future__ import annotations

import json
import re
import sys
from collections.abc import Iterator
from pathlib import Path

import pytest

from ....adapters.persistence.storage.master_key.active_session import close_active_bucket_session
from ....core.config import override_settings
from ....core.type_adapters import STR_KEYED_MAPPING_ADAPTER
from ....tests.cli_envelope import unwrap_schema_envelope
from .cli_runner import invoke_cached_cli
from .runtime_profile_cli_fixture import NativeCliProfileFixture, native_cli_profile_scope

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]


_PROFILE_FACTS = {
    "taxpayer_type.entity_type": "natural_person",
    "identity.name": "Native",
    "identity.surnames": "M145 CLI",
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
def native_m145_cli_profile(tmp_path: Path) -> Iterator[NativeCliProfileFixture]:
    with native_cli_profile_scope(tmp_path) as profile:
        profile.register(label="native-m145-cli-contract", facts=_PROFILE_FACTS)
        yield profile


def _invoke(args: list[str]):
    return invoke_cached_cli(args)


def _invoke_authenticated(profile: NativeCliProfileFixture, *command: str):
    assert profile.label is not None
    close_active_bucket_session()
    with override_settings(cadrumo_cli_reveal_identifiers=True):
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
        )
    assert profile.passphrase not in result.output
    return result


def _create_record_id(profile: NativeCliProfileFixture) -> str:
    result = _invoke_authenticated(profile, *_CREATE_ARGS)
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
    from ....core.i18n.render import tr

    assert payload["notices"] == [
        {
            "severity": "warning",
            "code": "config.login.session_not_persisted",
            "message": tr("cli.config.login.notices.session_invocation_scoped", locale="en"),
            "action": None,
            "context": None,
        }
    ]
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


@pytest.mark.windows_only
@pytest.mark.skipif(sys.platform != "win32", reason="requires native Windows profile workers")
def test_m145_create_requires_casilla_input(native_m145_cli_profile: NativeCliProfileFixture) -> None:
    result = _invoke_authenticated(native_m145_cli_profile, "app", "modelo", "m145", "create", "--year", "2026")

    assert result.exit_code != 0
    assert "--casilla" in result.output


@pytest.mark.windows_only
@pytest.mark.skipif(sys.platform != "win32", reason="requires native Windows profile workers")
def test_m145_missing_record_failure_uses_central_error_boundary(
    native_m145_cli_profile: NativeCliProfileFixture,
) -> None:
    result = _invoke_authenticated(native_m145_cli_profile, "app", "modelo", "m145", "validate", "0" * 12)

    assert result.exit_code == 2, result.output
    assert "Traceback" not in result.output
    error = _unwrap_error_envelope(result.output)
    assert error["code"] == "REFUSED_M145_COMMUNICATION_RECORD_NOT_FOUND"
    assert error["category"] == "REFUSED"
    assert error["context"] == {"communication_record_id": "000000000000"}


@pytest.mark.windows_only
@pytest.mark.skipif(sys.platform != "win32", reason="requires native Windows profile workers")
def test_m145_transition_failure_uses_central_error_boundary(
    native_m145_cli_profile: NativeCliProfileFixture,
) -> None:
    communication_record_id = _create_record_id(native_m145_cli_profile)

    result = _invoke_authenticated(
        native_m145_cli_profile,
        "app",
        "modelo",
        "m145",
        "mark-locally-completed",
        communication_record_id[:12],
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
