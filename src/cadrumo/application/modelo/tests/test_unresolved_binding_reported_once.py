"""A box whose source produced nothing is reported once, by its box, whichever producer noticed first.

The owning resolver may already have reported the binding as unresolved, and
staging reports every present-source binding left without a value against its
box. On Modelo 390's annual prorrata regularisation both happen; the filer must
see one note at one level, the box's, not a box-less one beside it.
"""

from __future__ import annotations

import pytest

from ....core.aggregation import BindingSourceKind
from ....core.external_constants import OutputLanguage
from ....core.modelo_work_progress_state import ModeloWorkProgressState
from ....core.period import Period
from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ....domain.calculations.registry.binding_targets import sole_bound_casilla
from ....domain.calculations.registry.schema import RegistrySnapshot
from ....domain.modelos.codes import ModeloCode
from ...aggregation.source_mesh import CalculationSourceDiagnostic, CalculationSourceResolution
from .._calculation_source_staging import add_expected_missing_binding_diagnostics
from ..work_form import build_modelo_work_form
from ..work_form_models import ModeloFormCalculationNote
from ..work_form_service import modelo_form_snapshot
from ..work_review import ModeloWorkProgress, ModeloWorkReview, build_modelo_work_review_casillas

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_YEAR = 2025
_REGULARISATION = "modelo-390-prorrata-regularizacion-anual"
_RESOLVER = BindingSourceKind.PRORRATA_REGULARIZACION.value


def _snapshot(operation: PinnedAuthorityOperation) -> RegistrySnapshot:
    period = Period.from_year_and_code(_YEAR, "0A")
    revision_id = str(operation.revision_for_context("390", filing_year=_YEAR, period="0A").id)
    return modelo_form_snapshot(operation, ModeloCode("390"), _YEAR, period, revision_id)


def _resolver_said(casilla_id: str | None) -> CalculationSourceResolution:
    """What the prorrata resolver returns when it has no provisional percentage to regularise from."""
    return CalculationSourceResolution(
        resolver_id=_RESOLVER,
        owned_sources=(BindingSourceKind.PRORRATA_REGULARIZACION,),
        unresolved_binding_ids=(_REGULARISATION,),
        diagnostics=(
            CalculationSourceDiagnostic(
                reason="unresolved_binding",
                source_kind=_RESOLVER,
                resolver_id=_RESOLVER,
                binding_id=_REGULARISATION,
                casilla_id=casilla_id,
                message="the regularisation needs a provisional percentage",
            ),
        ),
    )


def _notes_for(
    operation: PinnedAuthorityOperation,
    snapshot: RegistrySnapshot,
    diagnostics: tuple[CalculationSourceDiagnostic, ...],
) -> tuple[ModeloFormCalculationNote, ...]:
    review = ModeloWorkReview(
        bucket_id="13000000-0000-4000-8000-000000000391",
        modelo="390",
        filing_year=_YEAR,
        period=Period.from_year_and_code(_YEAR, "0A"),
        registry_revision_id=snapshot.revision.id,
        work_unit_id="f" * 64,
        calculation_revision_id=None,
        lifecycle_state=None,
        verification_outcome=None,
        progress=ModeloWorkProgress(state=ModeloWorkProgressState.UNDEFINED),
        casillas=build_modelo_work_review_casillas(snapshot=snapshot, revision=None, operation=operation),
        findings=(),
        blockers=(),
    )
    return build_modelo_work_form(
        review=review,
        snapshot=snapshot,
        layout=operation.form_layout("390", snapshot.revision.id),
        revision=None,
        permitted_surface=None,
        entered_casilla_ids=frozenset(),
        overridden_binding_ids=frozenset(),
        language=OutputLanguage.EN,
        calculation_diagnostics=diagnostics,
    ).calculation_notes


@pytest.mark.parametrize("named_by_the_resolver", [True, False], ids=["resolver-names-the-box", "resolver-bare"])
def test_the_390_regularisation_left_unresolved_reads_as_one_note_on_its_box(
    operation: PinnedAuthorityOperation, named_by_the_resolver: bool
) -> None:
    snapshot = _snapshot(operation)
    box = sole_bound_casilla(snapshot.revision, _REGULARISATION)
    assert box is not None, "the regularisation fills one box"

    staged = add_expected_missing_binding_diagnostics(
        snapshot.revision, _resolver_said(str(box) if named_by_the_resolver else None)
    )
    unresolved = [item for item in staged.diagnostics if item.reason == "unresolved_binding"]
    notes = [
        note for note in _notes_for(operation, snapshot, staged.diagnostics) if note.reason == "unresolved_binding"
    ]

    assert [(item.binding_id, item.casilla_id) for item in unresolved] == [(_REGULARISATION, box)]
    assert [note.casilla_id for note in notes] == [box]
    assert staged.unresolved_binding_ids == (_REGULARISATION,)
