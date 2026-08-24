"""Terminal-outcome contracts for the Google calculation-sheet adapters."""

from __future__ import annotations

import json
import subprocess
import sys
from collections.abc import Mapping
from typing import Any, cast

import pytest

from .....core import ActionConditionality, ActionEvidenceProvenance, NoRecoveryOutcome
from ...storage import OutboundStorageConflictError, OutboundStorageValidationError
from .._calc_sheets_pull import (
    _merge_developer_metadata_entries,
    _parse_relation_metadata,
    _read_developer_metadata,
    _verify_ownership,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_outbound_adapter]

_SPREADSHEET_ID = "spreadsheet-123"


def _assert_closed_outcome(
    error: BaseException,
    *,
    condition_id: str,
    facts: dict[str, str | int | bool],
    outcome: NoRecoveryOutcome,
) -> None:
    """Assert one observed, fact-only terminal verdict with no proposed action."""
    verdict = error.terminal_precondition_verdict
    assert verdict is not None
    assert verdict.failed_condition_id == condition_id
    assert len(verdict.evidence) == 1
    evidence = verdict.evidence[0]
    assert evidence.condition_id == condition_id
    assert evidence.evidence_id == f"{condition_id}.observation"
    assert evidence.provenance is ActionEvidenceProvenance.RUNTIME_OBSERVATION
    assert evidence.values == facts
    assert verdict.action is None
    assert verdict.argument_bindings == ()
    assert verdict.missing_argument_names == ()
    assert verdict.conditionality is ActionConditionality.NOT_APPLICABLE
    assert verdict.no_recovery_outcome is outcome


def _missing_google_client_outcome(*, module: str, call: str) -> dict[str, object]:
    """Run the optional-client refusal in a new interpreter without a patch seam."""
    script = f"""
import importlib.abc
import json
import sys

from {module} import {call}
from cadrumo.adapters.outbound.storage import OutboundStorageNetworkError


class _MissingGoogleApiFinder(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname == \"googleapiclient\" or fullname.startswith(\"googleapiclient.\"):
            raise ModuleNotFoundError(fullname)
        return None


finder = _MissingGoogleApiFinder()
sys.meta_path.insert(0, finder)
try:
    {call}(None)
except OutboundStorageNetworkError as error:
    verdict = error.terminal_precondition_verdict
else:
    raise AssertionError(\"the unavailable client did not refuse\")
finally:
    sys.meta_path.remove(finder)

assert verdict is not None
assert len(verdict.evidence) == 1
evidence = verdict.evidence[0]
print(json.dumps({{
    \"condition_id\": verdict.failed_condition_id,
    \"evidence_condition_id\": evidence.condition_id,
    \"evidence_id\": evidence.evidence_id,
    \"provenance\": evidence.provenance.value,
    \"values\": dict(evidence.values),
    \"action\": verdict.action,
    \"conditionality\": verdict.conditionality.value,
    \"outcome\": verdict.no_recovery_outcome.value,
}}))
"""
    completed = subprocess.run(
        (sys.executable, "-c", script),
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(completed.stdout)


def test_apply_missing_google_api_client_is_a_closed_safety_outcome() -> None:
    outcome = _missing_google_client_outcome(
        module="cadrumo.adapters.outbound.google._calc_sheets_apply",
        call="_drive_service",
    )

    assert outcome == {
        "condition_id": "google.calc_sheets.apply.api_client_available",
        "evidence_condition_id": "google.calc_sheets.apply.api_client_available",
        "evidence_id": "google.calc_sheets.apply.api_client_available.observation",
        "provenance": "runtime_observation",
        "values": {
            "client_available": False,
            "dependency": "google_api_python_client",
            "service_name": "drive",
            "service_version": "v3",
        },
        "action": None,
        "conditionality": "not_applicable",
        "outcome": "safety",
    }


@pytest.mark.parametrize(
    ("service", "service_name", "service_version"),
    (("_drive_service", "drive", "v3"), ("_sheets_service", "sheets", "v4")),
)
def test_pull_missing_google_api_client_is_a_closed_safety_outcome(
    service: str,
    service_name: str,
    service_version: str,
) -> None:
    outcome = _missing_google_client_outcome(
        module="cadrumo.adapters.outbound.google._calc_sheets_pull",
        call=service,
    )

    assert outcome == {
        "condition_id": "google.calc_sheets.pull.api_client_available",
        "evidence_condition_id": "google.calc_sheets.pull.api_client_available",
        "evidence_id": "google.calc_sheets.pull.api_client_available.observation",
        "provenance": "runtime_observation",
        "values": {
            "client_available": False,
            "dependency": "google_api_python_client",
            "service_name": service_name,
            "service_version": service_version,
        },
        "action": None,
        "conditionality": "not_applicable",
        "outcome": "safety",
    }


class _ResponseRequest:
    def __init__(self, response: dict[str, object]) -> None:
        self._response = response

    def execute(self, **_: object) -> dict[str, object]:
        return self._response


class _DriveFiles:
    def __init__(self, response: dict[str, object]) -> None:
        self._response = response

    def get(self, **_: object) -> _ResponseRequest:
        return _ResponseRequest(self._response)


class _DriveService:
    def __init__(self, response: dict[str, object]) -> None:
        self._response = response

    def files(self) -> _DriveFiles:
        return _DriveFiles(self._response)


class _SheetsSpreadsheets:
    def __init__(self, response: dict[str, object]) -> None:
        self._response = response

    def get(self, **_: object) -> _ResponseRequest:
        return _ResponseRequest(self._response)


class _SheetsService:
    def __init__(self, response: dict[str, object]) -> None:
        self._response = response

    def spreadsheets(self) -> _SheetsSpreadsheets:
        return _SheetsSpreadsheets(self._response)


def test_non_mapping_ownership_metadata_is_an_operator_decision() -> None:
    with pytest.raises(OutboundStorageValidationError) as raised:
        _verify_ownership(_DriveService({"appProperties": "not-a-mapping"}), _SPREADSHEET_ID)

    _assert_closed_outcome(
        raised.value,
        condition_id="google.calc_sheets.pull.ownership_metadata_valid",
        facts={"spreadsheet_id": _SPREADSHEET_ID, "ownership_metadata_mapping": False},
        outcome=NoRecoveryOutcome.OPERATOR_DECISION,
    )


def test_foreign_spreadsheet_is_a_state_divergence_operator_decision() -> None:
    with pytest.raises(OutboundStorageConflictError) as raised:
        _verify_ownership(_DriveService({"appProperties": {}}), _SPREADSHEET_ID)

    _assert_closed_outcome(
        raised.value,
        condition_id="google.calc_sheets.pull.ownership_aligned",
        facts={"spreadsheet_id": _SPREADSHEET_ID, "ownership_aligned": False},
        outcome=NoRecoveryOutcome.OPERATOR_DECISION,
    )


def test_non_list_developer_metadata_is_an_operator_decision() -> None:
    with pytest.raises(OutboundStorageValidationError) as raised:
        _read_developer_metadata(_SheetsService({"developerMetadata": {}}), _SPREADSHEET_ID)

    _assert_closed_outcome(
        raised.value,
        condition_id="google.calc_sheets.pull.developer_metadata_list_valid",
        facts={"spreadsheet_id": _SPREADSHEET_ID, "developer_metadata_list_valid": False},
        outcome=NoRecoveryOutcome.OPERATOR_DECISION,
    )


def test_non_mapping_developer_metadata_entry_is_an_operator_decision() -> None:
    entries = cast("tuple[Mapping[str, Any], ...]", ("not-a-mapping",))

    with pytest.raises(OutboundStorageValidationError) as raised:
        _merge_developer_metadata_entries(entries)

    _assert_closed_outcome(
        raised.value,
        condition_id="google.calc_sheets.pull.developer_metadata_entry_valid",
        facts={"metadata_entry_index": 0, "metadata_entry_mapping": False},
        outcome=NoRecoveryOutcome.OPERATOR_DECISION,
    )


def test_conflicting_developer_metadata_is_a_state_divergence_operator_decision() -> None:
    entries = (
        {"metadataKey": "cadrumo_registry_sha", "metadataValue": "old-registry-sha"},
        {"metadataKey": "cadrumo_registry_sha", "metadataValue": "new-registry-sha"},
    )

    with pytest.raises(OutboundStorageConflictError) as raised:
        _merge_developer_metadata_entries(entries)

    _assert_closed_outcome(
        raised.value,
        condition_id="google.calc_sheets.pull.developer_metadata_consistent",
        facts={"conflicting_metadata_key_count": 1, "metadata_consistent": False},
        outcome=NoRecoveryOutcome.OPERATOR_DECISION,
    )


@pytest.mark.parametrize(
    ("metadata", "condition_id", "facts"),
    (
        (
            "provenance=local_filing; legal_refs=Ley-35-2006:art-99; source_refs=boe-modelo-180-2023-form",
            "google.calc_sheets.pull.relation_legal_refs_valid",
            {
                "legal_refs_valid": False,
                "metadata_key": "legal_refs",
                "metadata_value": "Ley-35-2006:art-99",
            },
        ),
        (
            "provenance=local_filing; legal_refs=ley-35-2006:art-99; source_refs=ley-35-2006:art-99",
            "google.calc_sheets.pull.relation_source_refs_valid",
            {
                "metadata_key": "source_refs",
                "metadata_value": "ley-35-2006:art-99",
                "source_refs_valid": False,
            },
        ),
    ),
)
def test_malformed_provider_relation_reference_is_an_operator_decision(
    metadata: str,
    condition_id: str,
    facts: dict[str, str | int | bool],
) -> None:
    with pytest.raises(OutboundStorageValidationError) as raised:
        _parse_relation_metadata(metadata)

    _assert_closed_outcome(
        raised.value,
        condition_id=condition_id,
        facts=facts,
        outcome=NoRecoveryOutcome.OPERATOR_DECISION,
    )
