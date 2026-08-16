"""Installed-console recovery journeys for canonical Modelo action envelopes."""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from typing import Any

import pytest

from ....adapters.persistence.storage.sql import dispose_engine
from ....application.modelo import get_work_unit
from ....core import resolve_active_bucket_id
from ....core.config import SecretStoreBackend, load_settings, override_settings
from ....tests.profile_capsule import open_test_profile_session
from ....tests.user_profile import register_cli_profile
from .._verb_input_schema import build_verb_input_schemas, cli_argv_for

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_LOCALES = ("en", "es", "ca", "hu")
_CONSOLE = Path(__file__).resolve().parents[5] / ".venv" / "Scripts" / "aeat.exe"


def _console_environment(tmp_path: Path) -> tuple[dict[str, str], Path, Path]:
    """Build one subprocess-only encrypted profile environment."""
    storage_root = tmp_path / "storage"
    secret_store_dir = tmp_path / "secret-store"
    environment = {key: value for key, value in os.environ.items() if not key.startswith("CADRUMO_")}
    environment.update(
        {
            "CADRUMO_LOCAL_STORAGE_ROOT": str(storage_root),
            "CADRUMO_SECRET_STORE_BACKEND": "file",
            "CADRUMO_SECRET_STORE_DIR": str(secret_store_dir),
            "CADRUMO_SECRET_PASSPHRASE": load_settings().cadrumo_dev_test_database_password.get_secret_value(),
            "CADRUMO_OUTPUT_LANGUAGE": "en",
        },
    )
    return environment, storage_root, secret_store_dir


def _run_console(environment: dict[str, str], arguments: list[str]) -> subprocess.CompletedProcess[str]:
    """Run the installed console executable, never the in-process Click app."""
    assert _CONSOLE.is_file(), f"installed console is absent: {_CONSOLE}"
    return subprocess.run(  # noqa: S603 -- the installed test console and schema-derived argv are fixed test inputs.
        [_CONSOLE, "--format", "json", *arguments],
        cwd=_CONSOLE.parents[2],
        env=environment,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        check=False,
        timeout=90,
    )


def _document(run: subprocess.CompletedProcess[str]) -> dict[str, Any]:
    """Decode the emitted envelope regardless of its stdout/stderr channel."""
    for stream in (run.stdout, run.stderr):
        stripped = stream.strip()
        if not stripped:
            continue
        try:
            payload = json.loads(stripped)
        except json.JSONDecodeError:
            payload = None
        if isinstance(payload, dict):
            return payload
        for line in reversed(tuple(line for line in stream.splitlines() if line.strip())):
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(payload, dict):
                return payload
    raise AssertionError(f"console emitted no JSON document\nstdout={run.stdout}\nstderr={run.stderr}")


def _run_success(
    environment: dict[str, str],
    arguments: list[str],
    *,
    permitted_statuses: frozenset[str] = frozenset({"success"}),
) -> dict[str, Any]:
    run = _run_console(environment, arguments)
    assert run.returncode == 0, f"argv={arguments!r}\nstdout={run.stdout}\nstderr={run.stderr}"
    document = _document(run)
    assert document["status"] in permitted_statuses
    return document


def _result(document: dict[str, Any]) -> dict[str, Any]:
    result = document.get("result")
    assert isinstance(result, dict)
    return result


def _action_from_document(document: dict[str, Any]) -> dict[str, Any]:
    """Find the one recovery DTO from either refusal envelope shape."""
    error = document.get("error")
    if isinstance(error, dict):
        action = error.get("action")
        if isinstance(action, dict):
            return action
    result = document.get("result")
    if isinstance(result, dict):
        findings = result.get("findings")
        if isinstance(findings, list):
            actions = [
                row.get("action") for row in findings if isinstance(row, dict) and isinstance(row.get("action"), dict)
            ]
            assert len(actions) == 1
            return actions[0]
    raise AssertionError(f"document carries no actionable precondition: {document}")


def _dispatch_action(
    environment: dict[str, str],
    action: dict[str, Any],
) -> tuple[subprocess.CompletedProcess[str], list[str]]:
    """Execute an envelope action through its live schema, not a reconstructed command."""
    reference = action.get("action")
    assert isinstance(reference, dict)
    command_key = reference.get("target_command_key")
    cli_path = reference.get("cli_path")
    assert isinstance(command_key, str)
    assert isinstance(cli_path, list)

    schema = build_verb_input_schemas((command_key,))[command_key]
    assert list(schema.cli_path) == cli_path

    values: dict[str, object] = {}
    bindings = action.get("argument_bindings")
    assert isinstance(bindings, list)
    for binding in bindings:
        assert isinstance(binding, dict)
        assert binding["status"] == "resolved"
        name = binding["argument_name"]
        assert isinstance(name, str)
        assert name not in values
        values[name] = binding["value"]
    argv = cli_argv_for(schema, values)
    assert argv[: 2 + len(schema.cli_path)] == ["--format", "json", *cli_path]
    return _run_console(environment, argv[2:]), argv


def _create_natural_profile(environment: dict[str, str]) -> None:
    """Register the profile through the shared CLI registration door."""
    register_cli_profile(
        label="operadora-s27",
        facts={
            "taxpayer_type.entity_type": "natural_person",
            "taxpayer_type.irpf_income_categories": "actividad_economica",
            "identity.tax_id": "12345678Z",
            "identity.name": "Operadora",
            "identity.surnames": "Prueba",
            "activities.description": "actividad",
            "withholding.has_employees": "true",
        },
    )


def _create_legal_profile(environment: dict[str, str]) -> None:
    """Register the profile through the shared CLI registration door."""
    register_cli_profile(
        label="entidad-s27",
        facts={
            "taxpayer_type.entity_type": "legal_entity",
            "taxpayer_type.legal_entity_form": "sl",
            "identity.tax_id": "B12345674",
            "identity.legal_name": "Entidad de prueba SL",
            "activities.description": "actividad",
            "taxpayer_type.incn_prior_12_months": "500000",
            "censo.activity_start_date": "2024-01-15",
            "tax_residence.ccaa": "madrid",
            "iva.regime": "GENERAL",
        },
    )


def _create_work_unit(
    environment: dict[str, str],
    *,
    modelo: str,
    year: int,
    period: str,
    revision: str,
) -> str:
    document = _run_success(
        environment,
        [
            "app",
            "modelo",
            "work",
            "create",
            "--modelo",
            modelo,
            "--year",
            str(year),
            "--period",
            period,
            "--revision",
            revision,
        ],
    )
    work_unit_id = _result(document).get("work_unit_id")
    assert isinstance(work_unit_id, str)
    return work_unit_id


def _seed_m111_retencion(environment: dict[str, str]) -> None:
    observation = json.dumps(
        {
            "source_kind": "ledger_transaction",
            "source_object_id": "s27-retencion-001",
            "perceptor_nif": "A12345678",
            "perceptor_name": "Entidad pagadora SL",
            "scheme": "rendimientos_trabajo",
            "taxable_base": "1000.00",
            "retencion_amount": "190.00",
            "accrued_on": "2026-04-15",
        },
    )
    _run_success(
        environment,
        [
            "app",
            "modelo",
            "aggregate",
            "--modelo",
            "111",
            "--year",
            "2026",
            "--period",
            "2T",
            "--retencion-observation",
            observation,
        ],
    )


def _create_calculable_m111_work(environment: dict[str, str]) -> str:
    work_unit_id = _create_work_unit(
        environment,
        modelo="111",
        year=2026,
        period="2T",
        revision="2019-y-siguientes",
    )
    _seed_m111_retencion(environment)
    return work_unit_id


def _work_state(*, storage_root: Path, secret_store_dir: Path, work_unit_id: str) -> dict[str, Any]:
    """Load the persisted work-unit state through the production encrypted repository."""
    passphrase = load_settings().cadrumo_dev_test_database_password
    with override_settings(
        cadrumo_local_storage_root=storage_root,
        cadrumo_secret_store_backend=SecretStoreBackend.FILE,
        cadrumo_secret_store_dir=secret_store_dir,
        cadrumo_secret_passphrase=passphrase,
    ) as settings:
        dispose_engine(settings)
        try:
            bucket_id = resolve_active_bucket_id()
            assert bucket_id is not None
            with open_test_profile_session(bucket_id):
                work_unit = get_work_unit(work_unit_id)
            assert work_unit is not None
            return {
                "state": work_unit.state.value,
                "current_calculation_revision_id": work_unit.current_calculation_revision_id,
                "filed_calculation_revision_id": work_unit.filed_calculation_revision_id,
                "current_filing_record_id": work_unit.current_filing_record_id,
            }
        finally:
            dispose_engine(settings)


def _assert_action_id(action: dict[str, Any], action_id: str) -> None:
    reference = action.get("action")
    assert isinstance(reference, dict)
    assert reference.get("action_id") == action_id
    assert action.get("conditionality") == "immediate"
    assert action.get("no_recovery_outcome") is None


def test_installed_console_verify_calculate_retry_persists_verification(tmp_path: Path) -> None:
    environment, storage_root, secret_store_dir = _console_environment(tmp_path)
    _create_natural_profile(environment)
    work_unit_id = _create_calculable_m111_work(environment)
    original = ["app", "modelo", "work", "verify", work_unit_id]

    initial_run = _run_console(environment, original)
    assert initial_run.returncode != 0
    calculate_action = _action_from_document(_document(initial_run))
    _assert_action_id(calculate_action, "operator.modelo.work.calculate")
    calculation_run, calculation_argv = _dispatch_action(environment, calculate_action)
    assert calculation_run.returncode == 0, calculation_argv

    retried_run = _run_console(environment, original)
    assert retried_run.returncode == 0, retried_run.stderr
    retried = _document(retried_run)
    assert _result(retried)["calculation_revision_id"]
    assert (
        _work_state(
            storage_root=storage_root,
            secret_store_dir=secret_store_dir,
            work_unit_id=work_unit_id,
        )["current_calculation_revision_id"]
        is not None
    )


def test_installed_console_file_calculate_verify_retry_persists_filing(tmp_path: Path) -> None:
    environment, storage_root, secret_store_dir = _console_environment(tmp_path)
    _create_natural_profile(environment)
    work_unit_id = _create_calculable_m111_work(environment)
    original = ["app", "modelo", "work", "file", work_unit_id]

    initial_run = _run_console(environment, original)
    assert initial_run.returncode != 0
    calculate_action = _action_from_document(_document(initial_run))
    _assert_action_id(calculate_action, "operator.modelo.work.calculate")
    calculation_run, calculation_argv = _dispatch_action(environment, calculate_action)
    assert calculation_run.returncode == 0, calculation_argv

    before_verify = _work_state(storage_root=storage_root, secret_store_dir=secret_store_dir, work_unit_id=work_unit_id)
    structural_digests: dict[str, str] = {}
    verify_action: dict[str, Any] | None = None
    for locale in _LOCALES:
        draft_run = _run_console(environment, ["--language", locale, *original])
        assert draft_run.returncode != 0
        draft_document = _document(draft_run)
        current_action = _action_from_document(draft_document)
        _assert_action_id(current_action, "operator.modelo.work.verify")
        error = draft_document.get("error")
        assert isinstance(error, dict)
        structural_error = {key: value for key, value in error.items() if key != "message"}
        structural_digests[locale] = json.dumps(structural_error, sort_keys=True, ensure_ascii=False)
        if verify_action is None:
            verify_action = current_action
        else:
            assert current_action == verify_action
        assert (
            _work_state(storage_root=storage_root, secret_store_dir=secret_store_dir, work_unit_id=work_unit_id)
            == before_verify
        )
    assert len(set(structural_digests.values())) == 1
    assert verify_action is not None
    verify_run, verify_argv = _dispatch_action(environment, verify_action)
    assert verify_run.returncode == 0, verify_argv

    filed_run = _run_console(environment, original)
    assert filed_run.returncode == 0, filed_run.stderr
    filed = _result(_document(filed_run))
    assert filed["calculation_revision_id"]
    assert (
        _work_state(
            storage_root=storage_root,
            secret_store_dir=secret_store_dir,
            work_unit_id=work_unit_id,
        )["filed_calculation_revision_id"]
        == filed["calculation_revision_id"]
    )


def test_installed_console_required_bindings_action_is_decision_support_then_honest_retry(tmp_path: Path) -> None:
    environment, storage_root, secret_store_dir = _console_environment(tmp_path)
    _create_legal_profile(environment)
    work_unit_id = _create_work_unit(
        environment,
        modelo="202",
        year=2026,
        period="1P",
        revision="2025-y-siguientes",
    )
    original = ["app", "modelo", "work", "calculate", work_unit_id]
    before = _work_state(storage_root=storage_root, secret_store_dir=secret_store_dir, work_unit_id=work_unit_id)

    initial_run = _run_console(environment, original)
    assert initial_run.returncode != 0
    action = _action_from_document(_document(initial_run))
    _assert_action_id(action, "operator.modelo.bindings.list")
    discovery_run, discovery_argv = _dispatch_action(environment, action)
    assert discovery_run.returncode == 0, discovery_argv

    retry_run = _run_console(environment, original)
    assert retry_run.returncode != 0
    retry_action = _action_from_document(_document(retry_run))
    _assert_action_id(retry_action, "operator.modelo.bindings.list")
    assert (
        _work_state(storage_root=storage_root, secret_store_dir=secret_store_dir, work_unit_id=work_unit_id) == before
    )


def test_installed_console_discarded_work_is_terminal_in_every_locale(tmp_path: Path) -> None:
    environment, storage_root, secret_store_dir = _console_environment(tmp_path)
    _create_natural_profile(environment)
    work_unit_id = _create_work_unit(
        environment,
        modelo="111",
        year=2025,
        period="1T",
        revision="2019-y-siguientes",
    )
    _run_success(environment, ["app", "modelo", "work", "discard", work_unit_id, "--yes"])
    before = _work_state(storage_root=storage_root, secret_store_dir=secret_store_dir, work_unit_id=work_unit_id)
    structural_digests: dict[tuple[str, str], str] = {}

    for verb in ("calculate", "verify", "file"):
        for locale in _LOCALES:
            original = ["--language", locale, "app", "modelo", "work", verb, work_unit_id]
            first = _run_console(environment, original)
            assert first.returncode != 0
            document = _document(first)
            error = document.get("error")
            assert isinstance(error, dict)
            action = error.get("action")
            assert isinstance(action, dict)
            assert action["action"] is None
            assert action["no_recovery_outcome"] == "terminal"
            assert action["argument_bindings"] == []
            assert "suggestion" not in error
            message = error.get("message")
            assert isinstance(message, str)
            assert "aeat app" not in message.lower()
            # The rendered message is locale-specific; every other refusal field,
            # including terminal action and evidence structure, must be invariant.
            structural_error = {key: value for key, value in error.items() if key != "message"}
            structural_digests[(verb, locale)] = json.dumps(structural_error, sort_keys=True, ensure_ascii=False)

            retry = _run_console(environment, original)
            assert retry.returncode != 0
            assert _document(retry)["error"]["action"] == action
            assert (
                _work_state(storage_root=storage_root, secret_store_dir=secret_store_dir, work_unit_id=work_unit_id)
                == before
            )

    for verb in ("calculate", "verify", "file"):
        assert len({structural_digests[(verb, locale)] for locale in _LOCALES}) == 1
