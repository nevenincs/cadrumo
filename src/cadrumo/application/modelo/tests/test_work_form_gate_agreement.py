"""The form offers the file and the recording exactly where the application's own gates admit them.

Each case is a real calculation revision carrying one note, a Modelo 210 form
the real builder makes from it over the published registry, and the gate the
export and the local filing run on that same revision. Wherever the gate
refuses, the form holds the file back and never offers it next; wherever it
admits, a checked form offers the file. A declaration whose registry rules stop
short of calculation grade is halted through the read itself, and through its
public envelope.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID

import pytest

from ....core.external_constants import OutputLanguage
from ....core.period import Period
from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ....domain.calculations.registry.schema_references import RegistrySnapshotRef
from ....domain.calculations.registry.tax_id_format import runtime_tax_id_format
from ....domain.modelos.calculation_revision import (
    CalculationRevision,
    CalculationRevisionState,
    CalculationSourceIssue,
    derive_calculation_revision_id,
)
from ....domain.modelos.codes import ModeloCode
from ....domain.modelos.verification_report import VerificationCompletenessStatus
from ....domain.modelos.work_unit import WorkUnit, derive_work_unit_id
from ..calculation_note_gate import ModeloCalculationBlockedError, require_work_unit_calculation_unblocked
from ..calculation_notes import CHECK_REFUSED_REASONS, GATE_REFUSED_REASONS, PRINTED_BOX_REASONS
from ..edit_admission import RESPONSIBLE_OWNER
from ..edit_models import ModeloEditDomainRefusalV1, ModeloEditRefusalCode, ModeloEditRefusedV1
from ..work_form_header import export_hold
from ..work_form_models import ModeloWorkForm
from ..work_form_next_step import ModeloFormNextAction, form_next_step, result_fields
from ..work_form_service import ModeloWorkFormLoadV1
from ..workbench_projection import project_modelo_workbench_form
from ..workbench_read import ModeloWorkbenchFormReadV1
from .work_form_fixture import built_form, form_snapshot

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_BUCKET = "13000000-0000-4000-8000-000000000455"
_CLOCK = datetime(2026, 4, 2, 9, 0, tzinfo=UTC)
_HELD: dict[str, Decimal | str] = {"rendimientos_integros": Decimal("1200.00"), "tipo_renta": "01"}
_FILE_ACTIONS = frozenset(
    {ModeloFormNextAction.EXPORT, ModeloFormNextAction.EXPORT_AGAIN, ModeloFormNextAction.RECORD_AFTER_FILE}
)
_ADMITTED = "no_note"


def _work_unit(operation: PinnedAuthorityOperation) -> WorkUnit:
    period = Period.from_year_and_code(2025, "0A")
    revision_id = str(form_snapshot(operation, "210", 2025, "0A").revision.id)
    return WorkUnit(
        work_unit_id=derive_work_unit_id(
            bucket_id=_BUCKET, modelo="210", filing_year=2025, period=period, revision_id=revision_id
        ),
        bucket_id=_BUCKET,
        modelo=ModeloCode("210"),
        filing_year=2025,
        period=period,
        revision_id=revision_id,
        name="210-2025-0A",
        created_at=_CLOCK,
        updated_at=_CLOCK,
    )


def _revision(unit: WorkUnit, *issues: CalculationSourceIssue) -> CalculationRevision:
    return CalculationRevision(
        calculation_revision_id=derive_calculation_revision_id(
            work_unit_id=unit.work_unit_id,
            input_values_by_casilla_id={},
            binding_overrides={},
            casilla_values={},
            source_issues=issues,
            filing_instance_evidence=None,
            source_provenance=(),
        ),
        work_unit_id=unit.work_unit_id,
        registry_snapshot_ref=RegistrySnapshotRef(
            modelo="210", revision_id=unit.revision_id, modelo_year=2025, period="0A"
        ),
        state=CalculationRevisionState.BORRADOR,
        casilla_values={},
        observations=(),
        created_at=_CLOCK,
        updated_at=_CLOCK,
        filing_instance_evidence=None,
        source_provenance=(),
        source_issues=issues,
    )


_PRINTED_BOX = "rendimientos_integros"
"""A box the Modelo 210 form prints, for the reasons that withhold filing only on a printed box."""


def _issue(reason: str) -> CalculationSourceIssue:
    printed = {"casilla_id": _PRINTED_BOX} if reason in PRINTED_BOX_REASONS else {}
    return CalculationSourceIssue.model_validate(
        {"reason": reason, "binding_source": None, "message": f"the calculation noticed {reason}", **printed}
    )


def _checked_form(operation: PinnedAuthorityOperation, revision: CalculationRevision) -> ModeloWorkForm:
    """A checked form whose result boxes the calculation produced, so only the note can block it."""
    plain = built_form(operation, "210", 2025, "0A", held=_HELD, entered=frozenset(_HELD))
    results = {str(casilla_id): Decimal("0.00") for casilla_id in result_fields(plain)}
    form = built_form(
        operation, "210", 2025, "0A", held={**_HELD, **results}, entered=frozenset(_HELD), revision=revision
    )
    return form.model_copy(update={"verification": VerificationCompletenessStatus.COMPLETE})


def _gate_admits(unit: WorkUnit, revision: CalculationRevision, operation: PinnedAuthorityOperation) -> bool:
    try:
        require_work_unit_calculation_unblocked(work_unit=unit, revision=revision, action="export", operation=operation)
        require_work_unit_calculation_unblocked(work_unit=unit, revision=revision, action="file", operation=operation)
    except ModeloCalculationBlockedError:
        return False
    return True


@pytest.mark.parametrize("reason", [_ADMITTED, *sorted(GATE_REFUSED_REASONS - CHECK_REFUSED_REASONS)])
def test_the_form_offers_the_file_exactly_where_the_export_and_filing_gates_admit_it(
    operation: PinnedAuthorityOperation, reason: str
) -> None:
    unit = _work_unit(operation)
    revision = _revision(unit) if reason == _ADMITTED else _revision(unit, _issue(reason))
    form = _checked_form(operation, revision)

    admitted = _gate_admits(unit, revision, operation)
    hold = export_hold(form, OutputLanguage.EN, verified=True, recorded=False)
    step = form_next_step(form, verified=True, filed=False)

    assert admitted is (reason == _ADMITTED), reason
    assert (hold is None) is admitted, (reason, hold)
    assert (step.action in _FILE_ACTIONS) is admitted, (reason, step)


def _read(form: ModeloWorkForm, admission: ModeloEditRefusedV1, operation: PinnedAuthorityOperation):
    return ModeloWorkbenchFormReadV1(
        load=ModeloWorkFormLoadV1(form=form, verified=False, filed=False),
        admission=admission,
        calculation_revision_id=form.calculation_revision_id,
        verification_report_id=None,
        asks_m303_evidence=False,
        asks_modelo_390=False,
        registry_revision_id=form.registry_revision_id,
        tax_id_format=runtime_tax_id_format(authority=operation),
    )


def _refusal(*facts: str) -> ModeloEditRefusedV1:
    return ModeloEditRefusedV1(
        refusal=ModeloEditDomainRefusalV1(
            code=ModeloEditRefusalCode.ADMISSION_DENIED,
            facts=facts,
            responsible_owner=RESPONSIBLE_OWNER,
            reconsideration_condition="edit a modelo revision whose registry authority reaches calculation grade",
        )
    )


def test_rules_short_of_calculation_grade_halt_the_next_step_through_the_read(
    operation: PinnedAuthorityOperation,
) -> None:
    form = built_form(operation, "210", 2025, "0A", entered=frozenset())
    profile = UUID(_BUCKET)

    halted = _read(form, _refusal("registry_authority_grade"), operation)
    refused_otherwise = _read(form, _refusal("current_calculation_revision_id"), operation)

    assert halted.next_step is None
    assert project_modelo_workbench_form(profile, form.work_unit_id, halted).next_step is None
    assert refused_otherwise.next_step is not None
    public = project_modelo_workbench_form(profile, form.work_unit_id, refused_otherwise).next_step
    assert public is not None and public.action is ModeloFormNextAction.FILL
