"""Installed optional-extra refusals and overview remain distinct in every locale.

Two real wheel installs prove the point-of-use guard with and without the LLM
extra. The public overview console can refuse at a profile/session boundary;
that preceding refusal must remain distinct from an optional-extra failure.
"""

from __future__ import annotations

import json
import shutil
import sys
import textwrap
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import cast

import pytest

from cadrumo.core.external_constants import SUPPORTED_OUTPUT_LANGUAGES

from ..command_execution import CommandResult, run_command
from ..lane_verification_core import (
    build_companion_wheels,
    build_root_snapshot,
    build_wheel,
    create_pip_venv,
    install_targets_with_pip,
    isolated_product_env,
    venv_cadrumo_path,
    venv_python_path,
)

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint, pytest.mark.serial]

# dev/packaging/tests -> parents[3] is the repository root. Stated because
# the depth silently retargets on a move: these files carried the depth they
# had under src/, which resolved ABOVE the repository and built a wheel from
# a directory with no pyproject.
_REPO_ROOT = Path(__file__).resolve().parents[3]


@pytest.fixture(autouse=True)
def _repository_root_resolved() -> None:
    """Fail this module's tests if the depth arithmetic retargeted.

    Checked per test rather than at import. Collection must stay side-effect
    free, and a guard that raises during collection reports a broken module
    rather than a named gate that lost its root, which is harder to act on.
    """
    assert (_REPO_ROOT / "pyproject.toml").is_file(), f"packaging gate lost the repository root: {_REPO_ROOT}"


_MATRIX_MARKER = "S35_OPTIONAL_EXTRA_MATRIX:"


@dataclass(frozen=True)
class _InstalledCohort:
    """Two complete installed product environments with distinct extra states."""

    work_dir: Path
    core_python: Path
    llm_python: Path
    core_cli: Path


@pytest.fixture(scope="module")
def installed_cohort(tmp_path_factory: pytest.TempPathFactory) -> _InstalledCohort:
    """Build one source cohort and install it both without and with ``llm``."""
    uv = shutil.which("uv")
    assert uv is not None, "uv is required to build the installed action-envelope cohort"

    work_dir = tmp_path_factory.mktemp("overview-optional-extra-action-recovery")
    build_root = build_root_snapshot(_REPO_ROOT, work_dir)
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


def _run_optional_extra_matrix(*, work_dir: Path, python: Path, state_name: str) -> dict[str, object]:
    """Drive the real optional-extra guard and registered refusal renderers."""
    locales = json.dumps(SUPPORTED_OUTPUT_LANGUAGES)
    driver = textwrap.dedent(
        f"""
        import json
        from pathlib import Path

        import cadrumo
        from cadrumo.core.optional_extras import (
            LLM_EXTRA, MissingOptionalExtraError, optional_extra_available, require_optional_extra,
        )
        from cadrumo.core.config import override_settings
        from cadrumo.core.errors.error_codes import render_error_json, render_error_text

        matrix = {{}}
        for locale in {locales}:
            with override_settings(cadrumo_output_language=locale):
                try:
                    require_optional_extra(LLM_EXTRA)
                except MissingOptionalExtraError as error:
                    matrix[locale] = {{
                        "facts": error.context,
                        "error": json.loads(render_error_json(error)),
                        "text": render_error_text(error),
                    }}
                else:
                    matrix[locale] = {{"error": None, "text": None}}
        print(
            {_MATRIX_MARKER!r}
            + json.dumps(
                {{
                    "cadrumo_file": str(Path(cadrumo.__file__).resolve()),
                    "extra_available": optional_extra_available(LLM_EXTRA),
                    "matrix": matrix,
                }},
                ensure_ascii=True,
                sort_keys=True,
            )
        )
        """,
    )
    completed = run_command(
        [str(python), "-c", driver],
        cwd=work_dir,
        environment=_isolated_environment(work_dir, locale="en", state_name=state_name),
        errors="replace",
        timeout_seconds=None,
    )
    assert completed.returncode == 0, f"optional-extra driver failed:\n{completed.stdout}\n{completed.stderr}"
    line = next((item for item in completed.stdout.splitlines() if item.startswith(_MATRIX_MARKER)), None)
    assert line is not None, f"optional-extra driver emitted no matrix:\n{completed.stdout}\n{completed.stderr}"
    report = json.loads(line.removeprefix(_MATRIX_MARKER))
    assert isinstance(report, dict)
    return cast(dict[str, object], report)


def _object(value: object, *, label: str) -> dict[str, object]:
    """Narrow one decoded product JSON object without reimplementing its schema."""
    assert isinstance(value, dict), f"{label} is not an object: {value!r}"
    return cast(dict[str, object], value)


def _json_envelope(completed: CommandResult, *, command: str) -> dict[str, object]:
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
        json_result = run_command(
            [str(cohort.core_cli), "--format", "json", "app", "overview", "status"],
            cwd=cohort.work_dir,
            environment=_isolated_environment(cohort.work_dir, locale=locale, state_name=f"overview-{locale}"),
            errors="replace",
            timeout_seconds=None,
        )
        text_result = run_command(
            [str(cohort.core_cli), "--format", "text", "app", "overview", "status"],
            cwd=cohort.work_dir,
            environment=_isolated_environment(cohort.work_dir, locale=locale, state_name=f"overview-{locale}-text"),
            errors="replace",
            timeout_seconds=None,
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


def test_installed_optional_extra_guard_and_overview_refusals_remain_distinct(
    installed_cohort: _InstalledCohort,
) -> None:
    """Core absence refuses with a registered error; installing the extra admits the guard."""
    absent = _run_optional_extra_matrix(
        work_dir=installed_cohort.work_dir,
        python=installed_cohort.core_python,
        state_name="core-optional-extra",
    )
    present = _run_optional_extra_matrix(
        work_dir=installed_cohort.work_dir,
        python=installed_cohort.llm_python,
        state_name="llm-optional-extra",
    )

    assert Path(str(absent["cadrumo_file"])).is_relative_to(installed_cohort.core_python.parents[1])
    assert Path(str(present["cadrumo_file"])).is_relative_to(installed_cohort.llm_python.parents[1])
    assert absent["extra_available"] is False
    assert present["extra_available"] is True

    absent_matrix = _object(absent["matrix"], label="absent optional-extra matrix")
    present_matrix = _object(present["matrix"], label="present optional-extra matrix")
    assert set(absent_matrix) == set(SUPPORTED_OUTPUT_LANGUAGES)
    assert set(present_matrix) == set(SUPPORTED_OUTPUT_LANGUAGES)

    baseline: dict[str, object] | None = None
    for locale in SUPPORTED_OUTPUT_LANGUAGES:
        row = _object(absent_matrix[locale], label="absent optional-extra row")
        document = _object(row["error"], label="optional-extra error envelope")
        error = _object(document["error"], label="optional-extra refusal")
        assert error["code"] == "ERROR_OPTIONAL_EXTRA_MISSING"
        assert error["action"] is None
        assert row["facts"] == {
            "extra": "llm",
            "feature": "local-inference document reading",
            "import_name": "pynvml",
            "importable": False,
        }
        assert isinstance(error["message"], str) and error["message"].strip()
        assert isinstance(row["text"], str) and row["text"].strip()
        assert error["message"] in row["text"]
        context = _object(error["context"], label="rendered optional-extra context")
        assert context["import_name"] == "pynvml"
        assert context["importable"] == "false"
        structural = {key: value for key, value in error.items() if key != "message"}
        if baseline is None:
            baseline = structural
        else:
            assert structural == baseline
        assert present_matrix[locale] == {"error": None, "text": None}

    overview = _overview_console_matrix(installed_cohort)
    assert set(overview) == set(SUPPORTED_OUTPUT_LANGUAGES)
    overview_baseline: tuple[object, object] | None = None
    resolved_action_counts: set[int] = set()
    for locale in SUPPORTED_OUTPUT_LANGUAGES:
        row = overview[locale]
        document = _object(row["json"], label="overview JSON envelope")
        assert document["command"] == "overview.status"
        assert row["text_output_present"] is True
        assert row["json_exit_code"] == row["text_exit_code"]
        preceding_condition = _overview_precondition(document)
        overview_error = document.get("error")
        if isinstance(overview_error, dict):
            assert overview_error["code"] != "ERROR_OPTIONAL_EXTRA_MISSING"
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
