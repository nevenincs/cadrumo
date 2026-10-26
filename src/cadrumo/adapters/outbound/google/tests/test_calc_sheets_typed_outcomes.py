"""Terminal-outcome contracts for the Google calculation-sheet adapters."""

from __future__ import annotations

import json
import subprocess
import sys
from typing import TYPE_CHECKING, cast

import pytest

if TYPE_CHECKING:
    pass

from .....application.storage.calc_sheets.records import SheetExportPlan
from .....core.operator_action_enums import ActionConditionality, ActionEvidenceProvenance, NoRecoveryOutcome
from .....tests.google_credentials import unused_google_credentials
from ...storage.errors import OutboundStorageConflictError, OutboundStorageError, OutboundStorageValidationError
from ..calc_sheets_apply import apply_export_plan, preview_export_plan

pytestmark = [pytest.mark.unit, pytest.mark.hex_outbound_adapter, pytest.mark.usefixtures("operation")]

_SPREADSHEET_ID = "spreadsheet-123"


def _assert_closed_outcome(
    error: OutboundStorageError,
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


def _missing_google_client_outcome(*, imports: str, call: str) -> dict[str, object]:
    """Run the optional-client refusal in a new interpreter without a patch seam."""
    script = f"""
import importlib.abc
import json
import sys

{imports}
from cadrumo.adapters.outbound.storage.errors import OutboundStorageNetworkError


class _MissingGoogleApiFinder(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname == \"googleapiclient\" or fullname.startswith(\"googleapiclient.\"):
            raise ModuleNotFoundError(fullname)
        return None


finder = _MissingGoogleApiFinder()
sys.meta_path.insert(0, finder)
try:
    {call}
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
    payload = json.loads(completed.stdout)
    assert isinstance(payload, dict)
    assert all(isinstance(key, str) for key in payload)
    return {key: value for key, value in payload.items()}


def test_retired_template_apply_refuses_before_client_or_plan_access() -> None:
    with pytest.raises(OutboundStorageConflictError) as raised:
        apply_export_plan(
            cast(SheetExportPlan, object()), credentials=unused_google_credentials(), root_folder_id="root"
        )
    _assert_closed_outcome(
        raised.value,
        condition_id="google.managed_artifact.admitted",
        facts={"admitted": False, "reason": "selected_review_publication_required", "effect_uncertain": False},
        outcome=NoRecoveryOutcome.SAFETY,
    )


def test_apply_rejects_a_blank_root_folder_id_with_an_operator_decision() -> None:
    with pytest.raises(OutboundStorageValidationError) as raised:
        apply_export_plan(cast(SheetExportPlan, object()), credentials=unused_google_credentials(), root_folder_id="  ")

    _assert_closed_outcome(
        raised.value,
        condition_id="google.calc_sheets.apply.root_folder_id_valid",
        facts={"root_folder_id_present": False},
        outcome=NoRecoveryOutcome.OPERATOR_DECISION,
    )


def test_preview_rejects_a_blank_root_folder_id_with_the_same_operator_decision() -> None:
    with pytest.raises(OutboundStorageValidationError) as raised:
        preview_export_plan(
            cast(SheetExportPlan, object()), credentials=unused_google_credentials(), root_folder_id="  "
        )

    _assert_closed_outcome(
        raised.value,
        condition_id="google.calc_sheets.apply.root_folder_id_valid",
        facts={"root_folder_id_present": False},
        outcome=NoRecoveryOutcome.OPERATOR_DECISION,
    )


@pytest.mark.parametrize(
    ("builder", "service_name", "service_version"),
    (("drive_v3_service", "drive", "v3"), ("sheets_v4_service", "sheets", "v4")),
)
def test_each_shared_service_builder_names_its_service_when_the_client_is_missing(
    builder: str,
    service_name: str,
    service_version: str,
) -> None:
    outcome = _missing_google_client_outcome(
        imports="from cadrumo.adapters.outbound.google.api import drive_v3_service, sheets_v4_service",
        call=f'{builder}(None, unavailable_condition_id="google.calc_sheets.pull.api_client_available")',
    )

    assert outcome["condition_id"] == "google.calc_sheets.pull.api_client_available"
    assert outcome["values"] == {
        "client_available": False,
        "dependency": "google_api_python_client",
        "service_name": service_name,
        "service_version": service_version,
    }
    assert outcome["outcome"] == "safety"
