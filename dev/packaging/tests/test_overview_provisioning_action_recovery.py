"""Installed-product action-envelope proof for provisioning and overview.

The proof runs from two real wheel installs: a core-only cohort where the LLM
extra was never installed, and the same cohort with that declared extra.  It
does not alter import resolution.  The configuration DTO/text projection is
driven directly because the public console can legitimately refuse at an active
profile/session boundary before configuration rows or overview work are reached.
The public overview console is still invoked in every locale, and its preceding
typed refusal (when present) is kept distinct from provisioning outcomes.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import textwrap
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import cast

import pytest

from cadrumo.application.provisioning import ProvisioningPreconditionCondition
from cadrumo.core import NoRecoveryOutcome
from cadrumo.core.i18n import SUPPORTED_OUTPUT_LANGUAGES
from dev.packaging._smoke_common import (
    build_companion_wheels,
    build_wheel,
    create_pip_venv,
    head_extract,
    install_targets_with_pip,
    isolated_product_env,
    venv_cadrumo_path,
    venv_python_path,
)

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint, pytest.mark.serial]

_REPO_ROOT = Path(__file__).resolve().parents[5]
_PROVISIONING_MARKER = "S35_PROVISIONING_MATRIX:"


@dataclass(frozen=True)
class _InstalledCohort:
    """Two complete installed product environments with distinct extra states."""

    work_dir: Path
    core_python: Path
    llm_python: Path
    core_cli: Path


@pytest.fixture(scope="module")
def installed_cohort(tmp_path_factory: pytest.TempPathFactory) -> _InstalledCohort:
    """Build one committed cohort and install it both without and with ``llm``."""
    uv = shutil.which("uv")
    assert uv is not None, "uv is required to build the installed action-envelope cohort"

    work_dir = tmp_path_factory.mktemp("overview-provisioning-action-recovery")
    build_root = head_extract(_REPO_ROOT, work_dir)
    root_wheel = build_wheel(_REPO_ROOT, work_dir, uv, build_root=build_root)
    data_wheels = build_companion_wheels(work_dir, uv, build_root=build_root)
    targets = (str(root_wheel.resolve()), *(str(wheel.resolve()) for wheel in data_wheels))

    core_venv = create_pip_venv(work_dir, f"{sys.version_info.major}.{sys.version_info.minor}")
    install_targets_with_pip(work_dir, targets, core_venv)

    llm_work_dir = work_dir / "llm-extra"
    llm_work_dir.mkdir()
    llm_venv = create_pip_venv(llm_work_dir, f"{sys.version_info.major}.{sys.version_info.minor}")
    install_targets_with_pip(
        llm_work_dir,
        (f"{root_wheel.resolve()}[llm]", *(str(wheel.resolve()) for wheel in data_wheels)),
        llm_venv,
    )

    return _InstalledCohort(
        work_dir=work_dir,
        core_python=venv_python_path(core_venv),
        llm_python=venv_python_path(llm_venv),
        core_cli=venv_cadrumo_path(core_venv),
    )


def _isolated_environment(work_dir: Path, *, locale: str, state_name: str) -> dict[str, str]:
    """Run a product process outside the checkout and host configuration."""
    environment = isolated_product_env(work_dir / state_name)
    environment.pop("PYTHONPATH", None)
    environment["CADRUMO_OUTPUT_LANGUAGE"] = locale
    return environment


def _run_provisioning_matrix(*, work_dir: Path, python: Path, state_name: str) -> dict[str, object]:
    """Drive real producers plus the registered config-check JSON/text projection."""
    locales = json.dumps(SUPPORTED_OUTPUT_LANGUAGES)
    driver = textwrap.dedent(
        f"""
        import json
        from pathlib import Path

        import cadrumo
        from cadrumo.application.provisioning import (
            InstalledModel,
            probe_local_model_provisioning,
            probe_optional_extra,
        )
        from cadrumo.core import LLM_EXTRA, optional_extra_available
        from cadrumo.core.config import load_settings, override_settings
        from cadrumo.core.json_contract import validate_registered_result
        from cadrumo.entrypoints.cli._config._check_cli import _dependency_payload, _dependency_text_lines
        from cadrumo.entrypoints.cli._config._check_payloads import ConfigCheckResult

        def project(status):
            payload = _dependency_payload(status)
            result = ConfigCheckResult(ok=status.available, dependencies=[payload])
            registered = validate_registered_result("config.check", result)
            return {{
                "status": status.model_dump(mode="json"),
                "payload": payload.model_dump(mode="json"),
                "registered_result": registered.model_dump(mode="json"),
                "text": list(_dependency_text_lines(payload)),
            }}

        matrix = {{}}
        for locale in {locales}:
            with override_settings(cadrumo_output_language=locale):
                selected_model = load_settings().cadrumo_llm_ollama_vision_model
                matrix[locale] = [
                    project(probe_optional_extra(LLM_EXTRA)),
                    project(
                        probe_local_model_provisioning(
                            installed=(InstalledModel(name=selected_model, size_bytes=1),),
                        ),
                    ),
                ]
        print(
            {_PROVISIONING_MARKER!r}
            + json.dumps(
                {{
                    "cadrumo_file": str(Path(cadrumo.__file__).resolve()),
                    "extra_available": optional_extra_available(LLM_EXTRA),
                    "matrix": matrix,
                }},
                ensure_ascii=False,
                sort_keys=True,
            )
        )
        """,
    )
    completed = subprocess.run(  # noqa: S603 - fixed installed interpreter and test-owned driver source
        [str(python), "-c", driver],
        cwd=work_dir,
        env=_isolated_environment(work_dir, locale="en", state_name=state_name),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=180,
        check=False,
    )
    assert completed.returncode == 0, f"provisioning driver failed:\n{completed.stdout}\n{completed.stderr}"
    line = next((item for item in completed.stdout.splitlines() if item.startswith(_PROVISIONING_MARKER)), None)
    assert line is not None, f"provisioning driver emitted no matrix:\n{completed.stdout}\n{completed.stderr}"
    report = json.loads(line.removeprefix(_PROVISIONING_MARKER))
    assert isinstance(report, dict)
    return cast(dict[str, object], report)


def _object(value: object, *, label: str) -> dict[str, object]:
    """Narrow one decoded product JSON object without reimplementing its schema."""
    assert isinstance(value, dict), f"{label} is not an object: {value!r}"
    return cast(dict[str, object], value)


def _text_action_projection(lines: Iterable[object], *, service: str) -> dict[str, object]:
    """Read only the action cells emitted by the production text renderer."""
    prefix = f"{service}.precondition_action."
    projection: dict[str, object] = {}
    for item in lines:
        assert isinstance(item, str), f"text row is not a string: {item!r}"
        cell, encoded = item.split("\t", 1)
        if cell.startswith(prefix):
            projection[cell.removeprefix(prefix)] = json.loads(encoded)
    return projection


def _assert_projection_chain(row: Mapping[str, object], *, expected_condition: str | None) -> None:
    """Assert one producer reaches the registered JSON and text forms unchanged."""
    status = _object(row["status"], label="application status")
    payload = _object(row["payload"], label="CLI payload")
    registered_result = _object(row["registered_result"], label="registered result")
    assert payload["service"] == status["service"]
    assert payload["available"] == status["available"]
    assert payload["facts"] == status["facts"]
    assert registered_result["dependencies"] == [payload]

    action = payload["precondition_action"]
    if expected_condition is None:
        assert status["precondition_verdict"] is None
        assert action is None
        assert _text_action_projection(cast(Iterable[object], row["text"]), service=cast(str, payload["service"])) == {}
        return

    verdict = _object(status["precondition_verdict"], label="application verdict")
    resolved = _object(action, label="resolved action")
    assert verdict["failed_condition_id"] == expected_condition
    assert resolved["failed_condition_id"] == expected_condition
    evidence = resolved["evidence"]
    assert isinstance(evidence, list) and evidence
    assert all(_object(item, label="condition evidence")["values"] == status["facts"] for item in evidence)
    assert resolved["action"] is None
    assert resolved["no_recovery_outcome"] == NoRecoveryOutcome.OPERATOR_DECISION.value
    assert (
        _text_action_projection(cast(Iterable[object], row["text"]), service=cast(str, payload["service"])) == resolved
    )


def _json_envelope(completed: subprocess.CompletedProcess[str], *, command: str) -> dict[str, object]:
    """Recover the actual JSON error/success envelope without inspecting prose."""
    for stream in (completed.stdout, completed.stderr):
        try:
            document = json.loads(stream)
        except json.JSONDecodeError:
            pass
        else:
            if isinstance(document, dict) and document.get("command") == command:
                return cast(dict[str, object], document)
        for row in reversed(stream.splitlines()):
            try:
                candidate = json.loads(row)
            except json.JSONDecodeError:
                continue
            if isinstance(candidate, dict) and candidate.get("command") == command:
                return cast(dict[str, object], candidate)
    raise AssertionError(f"the console emitted no {command!r} JSON envelope: {completed.stdout!r} {completed.stderr!r}")


def _overview_console_matrix(cohort: _InstalledCohort) -> dict[str, dict[str, object]]:
    """Invoke the public overview surface in JSON and text for every locale."""
    matrix: dict[str, dict[str, object]] = {}
    for locale in SUPPORTED_OUTPUT_LANGUAGES:
        json_result = subprocess.run(  # noqa: S603 - fixed installed console argv
            [str(cohort.core_cli), "--format", "json", "app", "overview", "status"],
            cwd=cohort.work_dir,
            env=_isolated_environment(cohort.work_dir, locale=locale, state_name=f"overview-{locale}"),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=120,
            check=False,
        )
        text_result = subprocess.run(  # noqa: S603 - fixed installed console argv
            [str(cohort.core_cli), "--format", "text", "app", "overview", "status"],
            cwd=cohort.work_dir,
            env=_isolated_environment(cohort.work_dir, locale=locale, state_name=f"overview-{locale}-text"),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=120,
            check=False,
        )
        matrix[locale] = {
            "json_exit_code": json_result.returncode,
            "json": _json_envelope(json_result, command="overview.status"),
            "text_exit_code": text_result.returncode,
            "text_output_present": bool(text_result.stdout or text_result.stderr),
        }
    return matrix


def _assert_overview_notices_state_guidance_once(document: Mapping[str, object], *, locale: str) -> int:
    """Assert every overview notice carries guidance in exactly one honest form.

    An installed console in any locale must never state an executable command as
    prose: the localized message explains, and the executable identity lives on
    the resolved action with its live CLI path and materialised arguments. This
    is the installed-product half of the one-projection contract the unit-level
    rendering proof pins in-process.

    Returns:
        The number of notices carrying a fully resolved action.
    """
    notices = document.get("notices")
    if not isinstance(notices, list):
        return 0
    resolved_count = 0
    for item in notices:
        notice = _object(item, label=f"{locale} overview notice")
        message = notice["message"]
        assert isinstance(message, str) and message.strip(), f"{locale}: empty notice message"
        assert "aeat " not in message, f"{locale}: notice message states a command as prose: {message!r}"
        action = notice.get("action")
        if action is None:
            continue
        resolved = _object(action, label=f"{locale} notice action")
        reference = _object(resolved["action"], label=f"{locale} notice action reference")
        assert isinstance(reference["action_id"], str)
        assert isinstance(reference["target_command_key"], str)
        cli_path = reference["cli_path"]
        assert isinstance(cli_path, list) and cli_path, f"{locale}: notice action carries no live CLI path"
        assert all(isinstance(token, str) and not token.startswith("-") for token in cli_path)
        resolved_count += 1
    return resolved_count


def _overview_precondition(document: Mapping[str, object]) -> str | None:
    """Return a preceding typed console gate, if overview is not reached."""
    error = document.get("error")
    if not isinstance(error, dict):
        return None
    action = error.get("action")
    if not isinstance(action, dict):
        return None
    failed_condition = action.get("failed_condition_id")
    return failed_condition if isinstance(failed_condition, str) else None


@pytest.mark.timeout(900)
def test_real_optional_extra_outcomes_reach_config_json_and_text_without_an_overview_mixup(
    installed_cohort: _InstalledCohort,
) -> None:
    """Core absence and extra presence preserve typed no-recovery projections in all locales."""
    absent = _run_provisioning_matrix(
        work_dir=installed_cohort.work_dir,
        python=installed_cohort.core_python,
        state_name="core-provisioning",
    )
    present = _run_provisioning_matrix(
        work_dir=installed_cohort.work_dir,
        python=installed_cohort.llm_python,
        state_name="llm-provisioning",
    )

    assert Path(str(absent["cadrumo_file"])).is_relative_to(installed_cohort.core_python.parents[1])
    assert Path(str(present["cadrumo_file"])).is_relative_to(installed_cohort.llm_python.parents[1])
    assert absent["extra_available"] is False
    assert present["extra_available"] is True

    absent_matrix = _object(absent["matrix"], label="absent provisioning matrix")
    present_matrix = _object(present["matrix"], label="present provisioning matrix")
    assert set(absent_matrix) == set(SUPPORTED_OUTPUT_LANGUAGES)
    assert set(present_matrix) == set(SUPPORTED_OUTPUT_LANGUAGES)

    expected_absent_conditions = (
        ProvisioningPreconditionCondition.OPTIONAL_EXTRA_IMPORTABLE.value,
        ProvisioningPreconditionCondition.LOCAL_MODEL_MODEL_REQUIRES_EXTRA.value,
    )
    baseline: list[dict[str, object]] | None = None
    for locale in SUPPORTED_OUTPUT_LANGUAGES:
        rows = absent_matrix[locale]
        assert isinstance(rows, list)
        for row, condition in zip(rows, expected_absent_conditions, strict=True):
            _assert_projection_chain(_object(row, label="absent provisioning row"), expected_condition=condition)
        structural = [
            {key: value for key, value in _object(row, label="absent provisioning row").items() if key != "text"}
            for row in rows
        ]
        if baseline is None:
            baseline = structural
        else:
            assert structural == baseline

        available_rows = present_matrix[locale]
        assert isinstance(available_rows, list)
        for row, _condition in zip(available_rows, expected_absent_conditions, strict=True):
            _assert_projection_chain(_object(row, label="present provisioning row"), expected_condition=None)

    overview = _overview_console_matrix(installed_cohort)
    assert set(overview) == set(SUPPORTED_OUTPUT_LANGUAGES)
    provisioning_conditions = set(expected_absent_conditions)
    overview_baseline: tuple[object, object] | None = None
    resolved_action_counts: set[int] = set()
    for locale in SUPPORTED_OUTPUT_LANGUAGES:
        row = overview[locale]
        document = _object(row["json"], label="overview JSON envelope")
        assert document["command"] == "overview.status"
        assert row["text_output_present"] is True
        assert row["json_exit_code"] == row["text_exit_code"]
        preceding_condition = _overview_precondition(document)
        assert preceding_condition not in provisioning_conditions
        structural = (document["status"], preceding_condition)
        if overview_baseline is None:
            overview_baseline = structural
        else:
            assert structural == overview_baseline
        resolved_action_counts.add(_assert_overview_notices_state_guidance_once(document, locale=locale))

    # Prose is translated; executable identity is not. The count of fully
    # resolved actions is therefore a locale-invariant of the installed
    # product: a locale that resolved fewer would be one whose guidance had
    # decayed back into untranslatable command prose.
    assert len(resolved_action_counts) == 1
