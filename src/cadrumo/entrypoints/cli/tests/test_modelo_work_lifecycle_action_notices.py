"""Real CLI proof for canonical modelo-work lifecycle continuations."""

from __future__ import annotations

import json
from pathlib import Path
from typing import cast

import pytest
from click.testing import Result

from ....core.type_adapters import STR_KEYED_MAPPING_ADAPTER
from ....core.errors.error_codes import ErrorCategory, get_error_exit_code
from ....tests.cli_envelope import unwrap_envelope_notices as _notices
from ....tests.cli_runner import semantic_cli_output
from ._modelo_work_ux_support import _create_m130_work_unit, _create_profile, _invoke
from ._modelo_work_ux_support import _isolated_cli_backend as _isolated_cli_backend

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_LOCALES = ("en", "es", "ca", "hu")


def _notice(output: str, code: str) -> dict[str, object]:
    return STR_KEYED_MAPPING_ADAPTER.validate_python(next(item for item in _notices(output) if item["code"] == code))


def _discarded_work_evidence(work_unit_id: str) -> dict[str, str | int]:
    """Return the persisted facts shared by every discarded-state refusal."""
    return {
        "work_unit_id": work_unit_id,
        "work_unit_state": "descartado",
        "modelo": "130",
        "filing_year": 2025,
        "period": "1T",
        "revision_id": "2019-y-siguientes",
    }


def _assert_terminal_refusal(
    result: Result,
    *,
    command: str,
    failed_condition_id: str,
    evidence_id: str,
    work_unit_id: str,
) -> dict[str, object]:
    """Prove the real CLI preserved the application terminal verdict on the wire."""
    exit_code = result.exit_code
    stdout = result.stdout
    stderr = result.stderr
    output = result.output
    assert exit_code == get_error_exit_code(ErrorCategory.REFUSED), output
    assert stdout == ""
    document = STR_KEYED_MAPPING_ADAPTER.validate_json(stderr)
    assert document["command"] == command
    error = cast(dict[str, object], document["error"])
    assert "suggestion" not in error
    assert error["action"] == {
        "failed_condition_id": failed_condition_id,
        "evidence": [
            {
                "condition_id": failed_condition_id,
                "evidence_id": evidence_id,
                "provenance": "persisted_state",
                "values": _discarded_work_evidence(work_unit_id),
            },
        ],
        "action": None,
        "argument_bindings": [],
        "missing_argument_names": [],
        "conditionality": "not_applicable",
        "no_recovery_outcome": "terminal",
    }
    return document


def _discarded_natural_target() -> list[str]:
    """Return the exact natural key of the isolated discarded work unit."""
    return [
        "--modelo",
        "130",
        "--year",
        "2025",
        "--period",
        "1T",
        "--revision",
        "2019-y-siguientes",
    ]


def test_work_list_and_status_resolve_canonical_actions_with_localized_messages(
    _isolated_cli_backend: Path,
) -> None:
    """The application continuation drives a live, locale-neutral action envelope."""
    _create_profile()
    work_unit_id = _create_m130_work_unit()

    rendered_messages: set[str] = set()
    for locale in _LOCALES:
        listed = _invoke(
            [
                "--format",
                "json",
                "app",
                "modelo",
                "work",
                "list",
                "--output-language",
                locale,
            ],
        )
        assert listed.exit_code == 0, listed.output
        list_notice = _notice(listed.output, "modelo.work.list.next_action")
        assert list_notice["context"] == {
            "continuation_outcome": "action_available",
            "work_unit_count": "1",
            "work_unit_id": work_unit_id,
        }
        assert list_notice["action"] == {
            "action": {
                "action_id": "operator.modelo.work.status",
                "target_command_key": "modelo.work.status",
                "cli_path": ["app", "modelo", "work", "status"],
            },
            "argument_bindings": [
                {
                    "argument_name": "work_unit_id",
                    "status": "resolved",
                    "value": work_unit_id,
                    "source": "operator_action.verdict_context",
                    "source_key": "work_unit_id",
                    "source_evidence_id": None,
                },
            ],
        }
        assert "aeat " not in str(list_notice["message"]).lower()
        rendered_messages.add(str(list_notice["message"]))

        status = _invoke(
            [
                "--format",
                "json",
                "app",
                "modelo",
                "work",
                "status",
                work_unit_id,
                "--output-language",
                locale,
            ],
        )
        assert status.exit_code == 0, status.output
        status_notice = _notice(status.output, "modelo.work.status.next_action")
        assert status_notice["context"] == {
            "continuation_outcome": "action_available",
            "work_unit_id": work_unit_id,
            "work_unit_state": "borrador",
        }
        assert status_notice["action"] == {
            "action": {
                "action_id": "operator.modelo.work.calculate",
                "target_command_key": "modelo.work.calculate",
                "cli_path": ["app", "modelo", "work", "calculate"],
            },
            "argument_bindings": [
                {
                    "argument_name": "work_unit_id",
                    "status": "resolved",
                    "value": work_unit_id,
                    "source": "operator_action.verdict_context",
                    "source_key": "work_unit_id",
                    "source_evidence_id": None,
                },
            ],
        }
        assert "aeat " not in str(status_notice["message"]).lower()
        rendered_messages.add(str(status_notice["message"]))

    assert len(rendered_messages) == len(_LOCALES) * 2


def test_discarded_work_status_exposes_terminal_state_without_calculate_action(
    _isolated_cli_backend: Path,
) -> None:
    """A discarded unit has an explicit closed continuation and real calculate refusal."""
    _create_profile()
    work_unit_id = _create_m130_work_unit()

    discarded = _invoke(["--format", "json", "app", "modelo", "work", "discard", work_unit_id, "--yes"])
    assert discarded.exit_code == 0, discarded.output

    status = _invoke(["--format", "json", "app", "modelo", "work", "status", work_unit_id])
    assert status.exit_code == 0, status.output
    notice = _notice(status.output, "modelo.work.status.action_unavailable")
    assert notice["action"] is None
    assert notice["context"] == {
        "continuation_outcome": "terminal",
        "work_unit_id": work_unit_id,
        "work_unit_state": "descartado",
    }
    assert "aeat " not in str(notice["message"]).lower()

    calculate = _invoke(["--format", "json", "app", "modelo", "work", "calculate", work_unit_id])
    _assert_terminal_refusal(
        calculate,
        command="modelo.work.calculate",
        failed_condition_id="modelo.work.calculate.lifecycle.active",
        evidence_id="modelo.work.calculate.lifecycle.observation",
        work_unit_id=work_unit_id,
    )


def test_discarded_work_transport_guards_preserve_terminal_schema_and_state(
    _isolated_cli_backend: Path,
) -> None:
    """Every rejected discarded-state verb retains facts and terminal outcome on its real transport."""
    _create_profile()
    work_unit_id = _create_m130_work_unit()
    discarded = _invoke(["--format", "json", "app", "modelo", "work", "discard", work_unit_id, "--yes"])
    assert discarded.exit_code == 0, discarded.output

    natural_target = _discarded_natural_target()
    initial_status = _invoke(["--format", "json", "app", "modelo", "work", "status", work_unit_id])
    assert initial_status.exit_code == 0, initial_status.output
    initial_document = json.loads(initial_status.output)
    initial_result = cast(dict[str, object], initial_document["result"])
    assert initial_result["state"] == "descartado"

    for locale in _LOCALES:
        status = _invoke(
            [
                "--format",
                "json",
                "app",
                "modelo",
                "work",
                "status",
                *natural_target,
                "--output-language",
                locale,
            ],
        )
        assert status.exit_code == 0, status.output
        status_document = json.loads(status.output)
        status_result = cast(dict[str, object], status_document["result"])
        assert status_result["work_unit_id"] == work_unit_id
        assert status_result["state"] == "descartado"
        assert _notice(status.output, "modelo.work.status.action_unavailable")["action"] is None

        history = _invoke(
            [
                "--format",
                "json",
                "app",
                "modelo",
                "work",
                "history",
                *natural_target,
                "--output-language",
                locale,
            ],
        )
        assert history.exit_code == 0, history.output
        history_document = json.loads(history.output)
        history_result = cast(dict[str, object], history_document["result"])
        assert history_result["work_unit_id"] == work_unit_id

        calculate = _invoke(
            [
                "--format",
                "json",
                "app",
                "modelo",
                "work",
                "calculate",
                work_unit_id,
                "--output-language",
                locale,
            ],
        )
        calculate_document = _assert_terminal_refusal(
            calculate,
            command="modelo.work.calculate",
            failed_condition_id="modelo.work.calculate.lifecycle.active",
            evidence_id="modelo.work.calculate.lifecycle.observation",
            work_unit_id=work_unit_id,
        )
        message = cast(str, cast(dict[str, object], calculate_document["error"])["message"])
        assert "aeat " not in message.lower()
        assert "create" not in message.lower()

    calculate_natural = _invoke(
        ["--format", "json", "app", "modelo", "work", "calculate", *natural_target],
    )
    _assert_terminal_refusal(
        calculate_natural,
        command="modelo.work.calculate",
        failed_condition_id="modelo.work.calculate.lifecycle.active",
        evidence_id="modelo.work.calculate.lifecycle.observation",
        work_unit_id=work_unit_id,
    )

    create_same_target = _invoke(
        ["--format", "json", "app", "modelo", "work", "create", *natural_target],
    )
    _assert_terminal_refusal(
        create_same_target,
        command="modelo.work.create",
        failed_condition_id="modelo.work.create.lifecycle.target_available",
        evidence_id="modelo.work.create.lifecycle.observation",
        work_unit_id=work_unit_id,
    )

    rename = _invoke(
        ["--format", "json", "app", "modelo", "work", "rename", work_unit_id, "--name", "terminal rename"],
    )
    _assert_terminal_refusal(
        rename,
        command="modelo.work.rename",
        failed_condition_id="modelo.work.rename.lifecycle.mutable",
        evidence_id="modelo.work.rename.lifecycle.observation",
        work_unit_id=work_unit_id,
    )

    repeated_discard = _invoke(
        ["--format", "json", "app", "modelo", "work", "discard", work_unit_id, "--yes"],
    )
    _assert_terminal_refusal(
        repeated_discard,
        command="modelo.work.discard",
        failed_condition_id="modelo.work.discard.lifecycle.not_already_discarded",
        evidence_id="modelo.work.discard.lifecycle.observation",
        work_unit_id=work_unit_id,
    )

    imported = _invoke(
        [
            "--format",
            "json",
            "app",
            "modelo",
            "filing-record",
            "import",
            work_unit_id,
            "--evidence-kind",
            "aeat_csv_register",
            "--evidence-id",
            "discarded-state-observation",
            "--set",
            "1=0.00",
        ],
    )
    _assert_terminal_refusal(
        imported,
        command="modelo.filing_record.import",
        failed_condition_id="modelo.filing_record.import.lifecycle.active",
        evidence_id="modelo.filing_record.import.lifecycle.observation",
        work_unit_id=work_unit_id,
    )

    final_status = _invoke(["--format", "json", "app", "modelo", "work", "status", work_unit_id])
    assert final_status.exit_code == 0, final_status.output
    final_document = json.loads(final_status.output)
    final_result = cast(dict[str, object], final_document["result"])
    assert final_result["state"] == initial_result["state"]
    assert final_result["name"] == initial_result["name"]
    assert final_result["updated_at"] == initial_result["updated_at"]
    assert "suggestion:" not in semantic_cli_output(repeated_discard)
