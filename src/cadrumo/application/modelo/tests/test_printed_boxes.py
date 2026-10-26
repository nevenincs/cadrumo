"""Every surface that asks whether a box is printed gets the answer the form gives.

The form numbers a box from its published layout placement first. The gate on
filing, the notes that persist with a calculation and the level a note takes
read the same resolver, so a box the form prints with a number is a filed box
everywhere. Measured over every revision the authority reaches, and on the
Modelo 390 annual summary whose imports box [53] the form prints from its
placement alone.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from ....core.aggregation import BindingSourceKind
from ....core.external_constants import OutputLanguage
from ....core.modelo_work_progress_state import ModeloWorkProgressState
from ....core.period import Period, accepted_filing_period_codes
from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ....domain.calculations.registry.errors import EjercicioOrdenNotYetPublishedError, NoRevisionForPeriodError
from ....domain.calculations.registry.schema import RegistrySnapshot
from ....domain.calculations.registry.schema_references import RegistrySnapshotRef
from ....domain.modelos.calculation_revision import (
    CalculationRevision,
    CalculationRevisionState,
    CalculationSourceIssue,
    derive_calculation_revision_id,
)
from ....domain.modelos.codes import ModeloCode
from ...aggregation.source_mesh import CalculationSourceDiagnostic
from ..calculation_actions import _unrouted_source_issues
from ..calculation_note_gate import ModeloCalculationBlockedError, require_no_blocking_calculation_notes
from ..calculation_notes import note_attention
from ..printed_boxes import PrintedBoxes, printed_boxes, snapshot_printed_boxes
from ..work_form import build_modelo_work_form
from ..work_form_models import ModeloFormAttention, ModeloFormCasillaAddressV1, ModeloWorkForm
from ..work_form_service import modelo_form_snapshot
from ..work_review import ModeloWorkProgress, ModeloWorkReview, build_modelo_work_review_casillas

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_IMPORTS = "iva.anual.soportado.importaciones"
"""Modelo 390's IVA paid on imports, which the form prints as box [53] by its layout placement."""
_YEAR = 2025
_WORK_UNIT = "d" * 64
_CLOCK = datetime(2026, 1, 20, 9, 0, tzinfo=UTC)


def test_every_number_a_layout_placement_states_is_the_number_the_gate_reads(
    operation: PinnedAuthorityOperation,
) -> None:
    measured = 0
    disagreements: list[tuple[str, str, str, str | None]] = []
    for modelo in operation.modelo_ids():
        for year in operation.supported_filing_years().years:
            for code in accepted_filing_period_codes():
                try:
                    revision = operation.revision_for_context(modelo, filing_year=year, period=code)
                except (NoRevisionForPeriodError, EjercicioOrdenNotYetPublishedError):
                    continue
                layout = operation.form_layout(modelo, revision.id)
                if layout is None:
                    continue
                boxes = printed_boxes(revision, layout)
                for placement in layout.placements:
                    if placement.box_number is None:
                        continue
                    measured += 1
                    read = boxes.number(str(placement.casilla_id))
                    if read != placement.box_number:
                        disagreements.append((modelo, str(placement.casilla_id), placement.box_number, read))

    assert measured > 0, "the census reached no numbered placement, so it proves nothing"
    assert disagreements == []


def _m390_form_and_boxes(
    operation: PinnedAuthorityOperation,
) -> tuple[RegistrySnapshot, ModeloWorkForm, PrintedBoxes]:
    period = Period.from_year_and_code(_YEAR, "0A")
    revision_id = str(operation.revision_for_context("390", filing_year=_YEAR, period="0A").id)
    snapshot = modelo_form_snapshot(operation, ModeloCode("390"), _YEAR, period, revision_id)
    review = ModeloWorkReview(
        bucket_id="13000000-0000-4000-8000-000000000390",
        modelo="390",
        filing_year=_YEAR,
        period=period,
        registry_revision_id=snapshot.revision.id,
        work_unit_id=_WORK_UNIT,
        calculation_revision_id=None,
        lifecycle_state=None,
        verification_outcome=None,
        progress=ModeloWorkProgress(state=ModeloWorkProgressState.UNDEFINED),
        casillas=build_modelo_work_review_casillas(snapshot=snapshot, revision=None, operation=operation),
        findings=(),
        blockers=(),
    )
    form = build_modelo_work_form(
        review=review,
        snapshot=snapshot,
        layout=operation.form_layout("390", snapshot.revision.id),
        revision=None,
        permitted_surface=None,
        entered_casilla_ids=frozenset(),
        overridden_binding_ids=frozenset(),
        language=OutputLanguage.EN,
        calculation_diagnostics=(_unresolved_imports(),),
    )
    return snapshot, form, snapshot_printed_boxes(operation, snapshot)


def _unresolved_imports() -> CalculationSourceDiagnostic:
    return CalculationSourceDiagnostic(
        reason="unresolved_binding",
        source_kind=BindingSourceKind.LEDGER_IVA_AGGREGATION.value,
        casilla_id=_IMPORTS,
        message="the imports box's source produced no value",
    )


def test_the_gates_printed_boxes_are_the_boxes_the_390_form_numbers(operation: PinnedAuthorityOperation) -> None:
    _snapshot, form, boxes = _m390_form_and_boxes(operation)
    numbered_on_the_form = {
        str(field.address.casilla_id): field.box
        for field in form.fields()
        if isinstance(field.address, ModeloFormCasillaAddressV1) and field.box is not None
    }

    assert numbered_on_the_form, "the form numbered no box, so the comparison proves nothing"
    assert dict(boxes.numbers) == numbered_on_the_form


def test_an_unresolved_390_imports_box_blocks_is_stored_and_named_by_its_printed_number(
    operation: PinnedAuthorityOperation,
) -> None:
    snapshot, form, boxes = _m390_form_and_boxes(operation)
    note = next(note for note in form.calculation_notes if note.casilla_id == _IMPORTS)
    issues = _unrouted_source_issues((_unresolved_imports(),), boxes)
    revision = _revision_with(snapshot.revision.id, issues)

    with pytest.raises(ModeloCalculationBlockedError) as refused:
        require_no_blocking_calculation_notes(revision, action="export", boxes=boxes)

    assert boxes.number(_IMPORTS) == "53"
    assert note_attention("unresolved_binding", box=boxes.number(_IMPORTS)) is ModeloFormAttention.BLOCKS
    assert (note.attention, note.box) == (ModeloFormAttention.BLOCKS, "53")
    assert note in form.blocking_calculation_notes
    assert [(issue.reason, str(issue.casilla_id)) for issue in issues] == [("unresolved_binding", _IMPORTS)]
    assert (refused.value.context or {}).get("box") == "53"


def test_a_working_figure_the_390_form_does_not_number_is_neither_stored_nor_blocking(
    operation: PinnedAuthorityOperation,
) -> None:
    snapshot, _form, boxes = _m390_form_and_boxes(operation)
    working = next(str(casilla.id) for casilla in snapshot.revision.casillas if not boxes.prints(str(casilla.id)))
    diagnostic = _unresolved_imports().model_copy(update={"casilla_id": working})

    assert _unrouted_source_issues((diagnostic,), boxes) == ()
    assert note_attention("unresolved_binding", box=boxes.number(working)) is ModeloFormAttention.CHECK


def _revision_with(revision_id: str, issues: tuple[CalculationSourceIssue, ...]) -> CalculationRevision:
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
        registry_snapshot_ref=RegistrySnapshotRef(
            modelo="390", revision_id=revision_id, modelo_year=_YEAR, period="0A"
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
