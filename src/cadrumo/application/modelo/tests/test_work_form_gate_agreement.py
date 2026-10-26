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

from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from typing import get_args
from uuid import UUID

import pytest

from ....core.aggregation import BindingSourceKind
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
from ..calculation_notes import PRINTED_BOX_REASONS, note_attention
from ..edit_admission import RESPONSIBLE_OWNER
from ..edit_models import ModeloEditDomainRefusalV1, ModeloEditRefusalCode, ModeloEditRefusedV1
from ..work_form_header import ModeloFormExportHoldReason, export_hold
from ..work_form_issue_lines import form_issue_lines
from ..work_form_models import ModeloFormAttention, ModeloFormCasillaAddressV1, ModeloWorkForm
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


@dataclass(frozen=True, slots=True)
class _Note:
    """One note the calculation persists: its reason, the box it names and the binding source that raised it."""

    reason: str
    casilla_id: str | None = None
    binding_source: BindingSourceKind | None = None

    def issue(self) -> CalculationSourceIssue:
        return CalculationSourceIssue.model_validate(
            {
                "reason": self.reason,
                "binding_source": self.binding_source,
                "message": f"the calculation noticed {self.reason}",
                "casilla_id": self.casilla_id,
            }
        )


def _every_note() -> list[_Note]:
    """Every reason a calculation persists, which is all the gates read, each on a printed box where that matters."""
    reasons = get_args(CalculationSourceIssue.model_fields["reason"].annotation)
    return [_Note(reason, _PRINTED_BOX if reason in PRINTED_BOX_REASONS else None) for reason in sorted(reasons)]


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


def _agrees(operation: PinnedAuthorityOperation, note: _Note | None) -> None:
    unit = _work_unit(operation)
    revision = _revision(unit) if note is None else _revision(unit, note.issue())
    form = _checked_form(operation, revision)

    admitted = _gate_admits(unit, revision, operation)
    hold = export_hold(form, OutputLanguage.EN, verified=True, recorded=False)
    step = form_next_step(form, verified=True, filed=False)
    offered = step.action in _FILE_ACTIONS
    blocking_lines = [
        line for line in form_issue_lines(form, OutputLanguage.EN) if line.level is ModeloFormAttention.BLOCKS
    ]

    if not admitted:
        # What the gate refuses the form never offers: it holds the file, leads to resolving it and lists it.
        assert hold is not None and hold.reason is ModeloFormExportHoldReason.BLOCKS, (note, hold)
        assert step.action is ModeloFormNextAction.RESOLVE, (note, step)
        assert blocking_lines, note
        return
    attention = None if note is None else note_attention(note.reason, box=None if note.casilla_id is None else "x")
    if attention in {None, ModeloFormAttention.CHECK, ModeloFormAttention.INFO}:
        # Nothing the gate admits that only asks to be checked holds the file back.
        assert hold is None and offered, (note, hold, step)
    else:
        # A note the check or the export decides on its own, or a value still missing, keeps the file back here too.
        assert not offered, (note, step)


def test_a_form_with_no_note_offers_the_file_the_gates_admit(operation: PinnedAuthorityOperation) -> None:
    _agrees(operation, None)


@pytest.mark.parametrize("note", _every_note(), ids=lambda note: note.reason)
def test_every_note_kind_holds_the_file_exactly_where_the_export_and_filing_gates_refuse_it(
    operation: PinnedAuthorityOperation, note: _Note
) -> None:
    _agrees(operation, note)


def test_an_unresolved_working_figure_is_worth_checking_yet_held_as_the_gates_hold_it(
    operation: PinnedAuthorityOperation,
) -> None:
    form = built_form(operation, "210", 2025, "0A", entered=frozenset())
    unprinted = [
        str(field.address.casilla_id)
        for field in form.fields()
        if isinstance(field.address, ModeloFormCasillaAddressV1) and (field.box is None or field.box == "")
    ]
    assert unprinted, "the Modelo 210 form keeps some figure it does not print"
    for note in (_Note("unresolved_binding", unprinted[0]), _Note("unresolved_binding")):
        unit = _work_unit(operation)
        revision = _revision(unit, note.issue())
        checked = _checked_form(operation, revision)
        (shown,) = [item for item in checked.calculation_notes if item.reason == note.reason]

        assert not _gate_admits(unit, revision, operation), note
        assert shown.attention is ModeloFormAttention.CHECK and shown.withholds_filing, shown
        _agrees(operation, note)


def test_an_unrouted_one_stop_shop_row_is_the_modelo_369_checks_and_the_gates_admit_it(
    operation: PinnedAuthorityOperation,
) -> None:
    note = _Note("unrouted_observation", binding_source=BindingSourceKind.LEDGER_OSS_AGGREGATION)
    unit = _work_unit(operation)
    revision = _revision(unit, note.issue())

    assert _gate_admits(unit, revision, operation)
    (shown,) = _checked_form(operation, revision).calculation_notes
    assert not shown.withholds_filing
    _agrees(operation, note)


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
