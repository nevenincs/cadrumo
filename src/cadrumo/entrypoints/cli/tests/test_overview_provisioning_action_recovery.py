"""End-to-end typed recovery proof for the provisioning diagnostics cutover.

The development environment deliberately carries the local-model extra, so a
fresh interpreter makes its registered import unavailable *before* application
imports.  This is the actual import-resolution boundary used by the production
probe, not a replaced probe or a patched handler.  The driver then exercises
the application producer, S89's configuration-check DTO, its registered result
schema, and the text renderer together.

The real console command is separately observed in the step record: this
worktree's active profile refuses at the session boundary before configuration
checks can reach their dependency rows.  The handler/DTO path below is therefore
the deterministic proof for the provisioning rows themselves.
"""

from __future__ import annotations

import json
import subprocess
import sys
import textwrap
from collections.abc import Iterable, Mapping
from typing import cast

import pytest

from ....core import LLM_EXTRA, NoRecoveryOutcome
from ....core.i18n import SUPPORTED_OUTPUT_LANGUAGES

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_DRIVER_MARKER = "S35_PROVISIONING_MATRIX:"


def _run_provisioning_matrix(*, extra_unavailable: bool) -> dict[str, list[dict[str, object]]]:
    """Run production probes and their CLI projection in an isolated interpreter."""
    import_name = json.dumps(LLM_EXTRA.import_name)
    locales = json.dumps(SUPPORTED_OUTPUT_LANGUAGES)
    absent_setup = ""
    if extra_unavailable:
        absent_setup = f"""
        class OptionalExtraAbsentAtImportBoundary:
            def find_spec(self, fullname, path=None, target=None):
                if fullname.split('.', 1)[0] == {import_name}:
                    raise ModuleNotFoundError(name=fullname)
                return None

        for module_name in tuple(sys.modules):
            if module_name.split('.', 1)[0] == {import_name}:
                del sys.modules[module_name]
        sys.meta_path.insert(0, OptionalExtraAbsentAtImportBoundary())
        """
    driver = textwrap.dedent(
        f"""
        import json
        import sys

        {absent_setup}
        from cadrumo.application.provisioning import InstalledModel, probe_local_model_provisioning, probe_optional_extra
        from cadrumo.core import LLM_EXTRA
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
        print({_DRIVER_MARKER!r} + json.dumps(matrix, ensure_ascii=False, sort_keys=True))
        """,
    )
    completed = subprocess.run(  # noqa: S603 - fixed interpreter and test-owned driver source
        [sys.executable, "-c", driver],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=120,
        check=False,
    )
    assert completed.returncode == 0, f"provisioning driver failed:\n{completed.stdout}\n{completed.stderr}"
    line = next((item for item in completed.stdout.splitlines() if item.startswith(_DRIVER_MARKER)), None)
    assert line is not None, f"provisioning driver emitted no matrix:\n{completed.stdout}\n{completed.stderr}"
    matrix = json.loads(line.removeprefix(_DRIVER_MARKER))
    assert isinstance(matrix, dict)
    return cast(dict[str, list[dict[str, object]]], matrix)


def _object(value: object, *, label: str) -> dict[str, object]:
    """Narrow one decoded JSON object without inventing a presentation model."""
    assert isinstance(value, dict), f"{label} is not an object: {value!r}"
    return cast(dict[str, object], value)


def _text_action_projection(lines: Iterable[object], *, service: str) -> dict[str, object]:
    """Read the action cells emitted by the production text renderer."""
    prefix = f"{service}.precondition_action."
    projection: dict[str, object] = {}
    for item in lines:
        assert isinstance(item, str), f"text row is not a string: {item!r}"
        cell, encoded = item.split("\t", 1)
        if cell.startswith(prefix):
            projection[cell.removeprefix(prefix)] = json.loads(encoded)
    return projection


def _assert_projection_chain(
    row: Mapping[str, object],
    *,
    expected_condition: str | None,
) -> None:
    """Assert one real producer reaches both CLI forms through the same DTO."""
    status = _object(row["status"], label="application status")
    payload = _object(row["payload"], label="CLI payload")
    registered_result = _object(row["registered_result"], label="registered result")
    assert payload["service"] == status["service"]
    assert payload["available"] == status["available"]
    assert payload["facts"] == status["facts"]
    dependencies = registered_result["dependencies"]
    assert dependencies == [payload]

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
    assert isinstance(evidence, list) and len(evidence) == 1
    evidence_row = _object(evidence[0], label="condition evidence")
    assert evidence_row["values"] == status["facts"]
    assert resolved["action"] is None
    assert resolved["no_recovery_outcome"] == NoRecoveryOutcome.OPERATOR_DECISION.value
    assert (
        _text_action_projection(cast(Iterable[object], row["text"]), service=cast(str, payload["service"])) == resolved
    )
    serialized = json.dumps(row, ensure_ascii=False, sort_keys=True)
    assert LLM_EXTRA.install_hint not in serialized
    assert "suggestion" not in serialized
    assert "next_command" not in serialized


def test_unavailable_extra_and_stored_selected_models_emit_closed_recovery_in_every_locale() -> None:
    """Two distinct real provisioning failures stay closed and structurally identical across locales."""
    matrix = _run_provisioning_matrix(extra_unavailable=True)

    assert set(matrix) == set(SUPPORTED_OUTPUT_LANGUAGES)
    expected_conditions = (
        "provisioning.optional_extra.importable",
        "provisioning.local_model.model_requires_extra",
    )
    baseline: list[dict[str, object]] | None = None
    for locale in SUPPORTED_OUTPUT_LANGUAGES:
        rows = matrix[locale]
        assert len(rows) == len(expected_conditions)
        for row, condition in zip(rows, expected_conditions, strict=True):
            _assert_projection_chain(row, expected_condition=condition)
        structural = [{key: value for key, value in row.items() if key != "text"} for row in rows]
        if baseline is None:
            baseline = structural
        else:
            assert structural == baseline


def test_available_extra_and_selected_model_emit_no_recovery_in_every_locale() -> None:
    """The same production probes have no recovery DTO once both provisioning inputs are present."""
    matrix = _run_provisioning_matrix(extra_unavailable=False)

    assert set(matrix) == set(SUPPORTED_OUTPUT_LANGUAGES)
    for locale in SUPPORTED_OUTPUT_LANGUAGES:
        rows = matrix[locale]
        assert len(rows) == 2
        for row in rows:
            _assert_projection_chain(row, expected_condition=None)
