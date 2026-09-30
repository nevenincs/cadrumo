"""A persisted blocking calculation note refuses checking, exporting and recording; the check's own reasons are left to it.

The refusal is the application's, so every entrypoint meets it. It is worded
by the note's own catalogue sentence and names every blocking reason. Reasons
a check step adjudicates with its own evidence, such as an empty withholdings
detail the filer may attest, are not refused here, and a revision with no
blocking note passes.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import get_args

import pytest

from ....core.aggregation import BindingSourceKind
from ....core.config import override_settings
from ....domain.calculations.registry.schema_references import RegistrySnapshotRef
from ....domain.modelos.calculation_revision import (
    CalculationRevision,
    CalculationRevisionState,
    CalculationSourceIssue,
    derive_calculation_revision_id,
)
from ..calculation_note_gate import (
    ModeloCalculationBlockedError,
    blocking_calculation_issues,
    require_no_blocking_calculation_notes,
)
from ..calculation_notes import (
    BLOCKING_REASONS,
    CALCULATION_NOTE_ATTENTION,
    CHECK_REFUSED_REASONS,
    EXPORT_REFUSED_REASONS,
    GATE_REFUSED_REASONS,
)
from ..work_form_models import ModeloFormAttention

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_WORK_UNIT = "e" * 64
_CLOCK = datetime(2026, 4, 2, 9, 0, tzinfo=UTC)


def _revision(*issues: CalculationSourceIssue) -> CalculationRevision:
    return CalculationRevision(
        calculation_revision_id=derive_calculation_revision_id(
            work_unit_id=_WORK_UNIT,
            input_values_by_casilla_id={},
            binding_overrides={},
            casilla_values={},
            source_issues=issues,
            filing_instance_evidence=None,
            source_provenance=(),
        ),
        work_unit_id=_WORK_UNIT,
        registry_snapshot_ref=RegistrySnapshotRef(modelo="130", revision_id="2026", modelo_year=2026, period="1T"),
        state=CalculationRevisionState.BORRADOR,
        casilla_values={},
        observations=(),
        created_at=_CLOCK,
        updated_at=_CLOCK,
        filing_instance_evidence=None,
        source_provenance=(),
        source_issues=issues,
    )


def _issue(reason: str, **fields: object) -> CalculationSourceIssue:
    return CalculationSourceIssue.model_validate(
        {"reason": reason, "binding_source": None, "message": f"the calculation noticed {reason}", **fields}
    )


def test_a_blocking_note_refuses_with_its_own_sentence_and_names_every_reason() -> None:
    revision = _revision(
        _issue("unrouted_declarable_quantity", binding_source=BindingSourceKind.LEDGER_IVA_AGGREGATION),
        _issue("invoice_reverse_charge_cuota_not_derivable"),
    )

    with override_settings(cadrumo_output_language="en"), pytest.raises(ModeloCalculationBlockedError) as refused:
        require_no_blocking_calculation_notes(revision, action="export")

    error = refused.value
    context = error.context or {}
    assert error.code.code == "REFUSED_MODELO_CALCULATION_BLOCKED"
    assert context["reasons"] == "invoice_reverse_charge_cuota_not_derivable,unrouted_declarable_quantity"
    assert context["action"] == "export"
    assert error.translated_message == "application.modelo.calc_diagnostic.unrouted_declarable_quantity.what"


@pytest.mark.parametrize(
    "issue",
    [
        _issue("withholding_detail_absent", binding_source=BindingSourceKind.WITHHOLDING),
        _issue("iva_selected_scope_evidence_failure", binding_source=BindingSourceKind.LEDGER_IVA_AGGREGATION),
        _issue("unrouted_observation", binding_source=BindingSourceKind.LEDGER_OSS_AGGREGATION),
    ],
    ids=["withholding-attestable", "iva-evidence", "oss-unrouted"],
)
def test_a_reason_the_check_adjudicates_itself_is_left_to_the_check(issue: CalculationSourceIssue) -> None:
    assert blocking_calculation_issues(_revision(issue)) == ()
    require_no_blocking_calculation_notes(_revision(issue), action="file")


def test_a_revision_with_no_blocking_note_passes() -> None:
    """Teeth for the refusal above: the same call on a clean revision does not refuse."""
    require_no_blocking_calculation_notes(_revision(), action="verify")
    assert blocking_calculation_issues(
        _revision(_issue("unrouted_observation", binding_source=BindingSourceKind.LEDGER_IVA_AGGREGATION))
    )


def test_the_editor_blocks_on_exactly_the_reasons_the_application_refuses() -> None:
    """One definition: the editor's blocking level, and the gate, check steps and export that refuse."""
    blocking_level = {
        reason for reason, level in CALCULATION_NOTE_ATTENTION.items() if level is ModeloFormAttention.BLOCKS
    }
    persisted = get_args(CalculationSourceIssue.model_fields["reason"].annotation)
    refused_by_the_gate = {
        reason
        for reason in persisted
        if blocking_calculation_issues(
            _revision(_issue(reason, binding_source=BindingSourceKind.LEDGER_IVA_AGGREGATION))
        )
    }

    assert blocking_level == BLOCKING_REASONS == GATE_REFUSED_REASONS | CHECK_REFUSED_REASONS | EXPORT_REFUSED_REASONS
    assert refused_by_the_gate == set(GATE_REFUSED_REASONS)
