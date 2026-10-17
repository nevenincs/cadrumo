"""End-to-end action-envelope coverage for mistaken Modelo work-unit selectors."""

from __future__ import annotations

import json

import pytest

from cadrumo.adapters.persistence.storage.tests.secure_sql import (
    isolated_cli_backend as _isolated_cli_backend,
)
from cadrumo.core.type_adapters import STR_KEYED_MAPPING_ADAPTER
from cadrumo.entrypoints.cli.tests.modelo_work_scenarios import (
    create_m130_work_unit,
    create_modelo_operator_profile,
    invoke_modelo_scenario_cli,
)

from .cli_runner import semantic_cli_output
from .modelo_profile_seed import seed_profile

__all__ = ["_isolated_cli_backend", "seed_profile"]

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint, pytest.mark.usefixtures("seed_profile")]

_LOCALES = ("en", "es", "ca", "hu")
_VERBS = ("verify", "file")


def _refusal_document(*, locale: str, verb: str, work_unit_id: str) -> dict[str, object]:
    """Invoke one real CLI rejection and parse its strict JSON error envelope."""
    result = invoke_modelo_scenario_cli(
        [
            "--language",
            locale,
            "--format",
            "json",
            "app",
            "modelo",
            "work",
            verb,
            work_unit_id,
        ],
    )
    assert result.exit_code != 0, result.output
    document = STR_KEYED_MAPPING_ADAPTER.validate_json(semantic_cli_output(result))
    assert document["status"] == "error"
    assert document["command"] == f"modelo.work.{verb}"
    return document


def _assert_calculate_recovery(document: dict[str, object], *, verb: str, work_unit_id: str) -> str:
    """Assert only the canonical action DTO, never localized command prose."""
    error = document["error"]
    assert isinstance(error, dict)
    action = error["action"]
    assert isinstance(action, dict), document
    assert action["failed_condition_id"] == f"modelo.work.{verb}.calculation_revision.addresses_calculation"
    assert action["conditionality"] == "immediate"
    assert action["no_recovery_outcome"] is None
    assert action["action"] == {
        "action_id": "operator.modelo.work.calculate",
        "target_command_key": "modelo.work.calculate",
        "cli_path": ["aeat", "app", "modelo", "work", "calculate"],
    }
    assert action["argument_bindings"] == [
        {
            "argument_name": "work_unit_id",
            "status": "resolved",
            "value": work_unit_id,
            "source": "operator_action.verdict_context",
            "source_key": "work_unit_id",
            "source_evidence_id": None,
        },
    ]
    assert action["missing_argument_names"] == []
    message = error["message"]
    assert isinstance(message, str)
    return message


def _assert_terminal_refusal(document: dict[str, object], *, verb: str) -> str:
    """Assert an explicitly closed outcome cannot advertise an executable action."""
    error = document["error"]
    assert isinstance(error, dict)
    action = error["action"]
    assert isinstance(action, dict), document
    assert action["failed_condition_id"] == f"modelo.work.{verb}.calculation_revision.addresses_calculation"
    assert action["conditionality"] == "not_applicable"
    assert action["action"] is None
    assert action["argument_bindings"] == []
    assert action["missing_argument_names"] == []
    assert action["no_recovery_outcome"] == "terminal"
    message = error["message"]
    assert isinstance(message, str)
    return message


def _assert_address_absent_refusal(
    document: dict[str, object],
    *,
    verb: str,
    condition: str,
    evidence_values: dict[str, object],
) -> str:
    """Unknown targets grant neither private admission nor a recovery disclosure."""
    error = document["error"]
    assert isinstance(error, dict)
    assert error["code"] == "REFUSED_RUNTIME_FRONTEND", document
    assert error["action"] is None, document
    assert error["context"] == {"reason": "operation_denied", "request_faults": "", "sign_in": "null"}
    # The caller's supplied address is not authority to disclose persisted
    # candidates, nor has an operation been admitted to mint a receipt.
    for value in evidence_values.values():
        if value:
            assert str(value) not in str(error["context"])
    message = error["message"]
    assert isinstance(message, str)
    return message


def test_verify_and_file_mistaken_work_unit_selectors_project_canonical_localized_actions() -> None:
    """Both verbs preserve the application verdict across all supported locales and lifecycle states."""
    create_modelo_operator_profile()
    work_unit_id = create_m130_work_unit()

    active_messages: dict[tuple[str, str], str] = {}
    for locale in _LOCALES:
        for verb in _VERBS:
            active_messages[(locale, verb)] = _assert_calculate_recovery(
                _refusal_document(locale=locale, verb=verb, work_unit_id=work_unit_id),
                verb=verb,
                work_unit_id=work_unit_id,
            )
    assert len({message for message in active_messages.values()}) == len(_LOCALES)

    discarded = invoke_modelo_scenario_cli(["app", "modelo", "work", "discard", work_unit_id, "--yes"])
    assert discarded.exit_code == 0, discarded.output

    terminal_messages: dict[tuple[str, str], str] = {}
    for locale in _LOCALES:
        for verb in _VERBS:
            terminal_messages[(locale, verb)] = _assert_terminal_refusal(
                _refusal_document(locale=locale, verb=verb, work_unit_id=work_unit_id),
                verb=verb,
            )
    assert len({message for message in terminal_messages.values()}) == len(_LOCALES)


def test_verify_and_file_absent_targets_report_declared_no_action_envelopes_in_all_locales() -> None:
    """Natural and exact absent addresses are application verdicts, not CLI hints."""
    create_modelo_operator_profile()

    natural_messages: dict[tuple[str, str], str] = {}
    for locale in _LOCALES:
        for verb in _VERBS:
            result = invoke_modelo_scenario_cli(
                [
                    "--language",
                    locale,
                    "--format",
                    "json",
                    "app",
                    "modelo",
                    "work",
                    verb,
                    "--modelo",
                    "130",
                    "--year",
                    "2025",
                    "--period",
                    "1T",
                ],
            )
            assert result.exit_code != 0, result.output
            document = json.loads(semantic_cli_output(result))
            natural_messages[(locale, verb)] = _assert_address_absent_refusal(
                document,
                verb=verb,
                condition="work_address.resolved",
                evidence_values={
                    "modelo": "130",
                    "filing_year": 2025,
                    "period": "1T",
                    "registry_revision_id": "",
                    "bucket_id": "",
                },
            )

    missing_work_unit_id = "f" * 64
    exact_messages: dict[tuple[str, str], str] = {}
    for locale in _LOCALES:
        for verb in _VERBS:
            result = invoke_modelo_scenario_cli(
                [
                    "--language",
                    locale,
                    "--format",
                    "json",
                    "app",
                    "modelo",
                    "work",
                    verb,
                    "--work-unit-id",
                    missing_work_unit_id,
                ],
            )
            assert result.exit_code != 0, result.output
            document = json.loads(semantic_cli_output(result))
            exact_messages[(locale, verb)] = _assert_address_absent_refusal(
                document,
                verb=verb,
                condition="work_address.resolved",
                evidence_values={
                    "work_unit_id": missing_work_unit_id,
                    "bucket_id": "",
                    "selector_kind": "work_unit_id",
                },
            )

    assert set(natural_messages.values()) == {"operation_denied"}
    assert set(exact_messages.values()) == {"operation_denied"}
