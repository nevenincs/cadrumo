"""The editor form classifies every casilla of a real revision exactly once.

The review rows, labels, help, completeness manifest and bindings come from the
published registry for modelo 130; only the layout is declared here, as small
as each assertion needs, because the join under test is what this module owns.
Expectations are stated from the registry's own declarations (a ledger-bound
box is fixed at its source, a previous-filing carry may be overridden, a
calculated box is never editable), not read back from the builder.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from ....core.external_constants import OutputLanguage
from ....core.modelo_work_progress_state import ModeloWorkProgressState
from ....core.period import Period
from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ....domain.calculations.registry.schema import RegistrySnapshot
from ....domain.calculations.registry.schema_base import CasillaDataType
from ....domain.calculations.registry.schema_form_layouts import (
    FORM_LAYOUT_GENERATOR_VERSION,
    FormCell,
    FormCellKind,
    FormFieldBlock,
    FormGridBlock,
    FormGridColumn,
    FormGridRow,
    FormLayoutDefinition,
    FormLayoutSeedSource,
    FormPageDefinition,
    FormPlacementDefinition,
    FormPlacementKind,
    FormSectionDefinition,
    FormUnplacedReason,
)
from ....domain.filing.schema import ModeloValueKind
from ..edit_models import (
    ModeloEditBindingIntentKind,
    ModeloEditNonWritableReason,
    ModeloEditNonWritableScalarSurfaceEntryV1,
    ModeloEditPermittedSurfaceEntryV1,
    ModeloEditScalarIntentKind,
    ModeloEditWritableBindingOverrideSurfaceEntryV1,
    ModeloEditWritableScalarSurfaceEntryV1,
)
from ..edit_value_grammar import binding_value_grammar, casilla_value_grammar
from ..work_form import ModeloWorkFormLayoutError, build_modelo_work_form
from ..work_form_models import (
    ModeloFormCasillaAddressV1,
    ModeloFormEditability,
    ModeloFormField,
    ModeloFormGridBlock,
    ModeloFormInspectionReason,
    ModeloFormLayoutProvenance,
    ModeloFormOrigin,
    ModeloFormTextDisclosure,
    ModeloWorkForm,
    address_key,
)
from ..work_review import ModeloWorkProgress, ModeloWorkReview, build_modelo_work_review_casillas

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_MODELO = "130"
_YEAR = 2026
_PERIOD = "1T"
_WORKING = "saldo-negativo-fin-periodo"
_UNPLACED = "19"
_SECTION_TWO = ("08", "09", "10", "11", "12", "13", "14", "15", "16", "17", "18")


@pytest.fixture
def snapshot(operation: PinnedAuthorityOperation) -> RegistrySnapshot:
    return operation.snapshot(_MODELO, filing_year=_YEAR, period=_PERIOD)


def _review(snapshot: RegistrySnapshot, operation: PinnedAuthorityOperation) -> ModeloWorkReview:
    return ModeloWorkReview(
        bucket_id="13000000-0000-4000-8000-000000000451",
        modelo=_MODELO,
        filing_year=_YEAR,
        period=Period.from_year_and_code(_YEAR, _PERIOD),
        registry_revision_id=snapshot.revision.id,
        work_unit_id="a" * 64,
        calculation_revision_id=None,
        lifecycle_state=None,
        verification_outcome=None,
        progress=ModeloWorkProgress(state=ModeloWorkProgressState.UNDEFINED),
        casillas=build_modelo_work_review_casillas(snapshot=snapshot, revision=None, operation=operation),
        findings=(),
        blockers=(),
    )


def _layout(
    snapshot: RegistrySnapshot, *, placements: tuple[FormPlacementDefinition, ...] | None = None
) -> FormLayoutDefinition:
    grid = FormGridBlock(
        id="grid",
        columns=(
            FormGridColumn(key="base", heading_key="modelo.form.column.base_imponible"),
            FormGridColumn(key="tipo", heading_key="modelo.form.column.tipo", official_heading="Tipo"),
        ),
        rows=(
            FormGridRow(
                key="r1",
                heading_key="modelo.schema.130.form.test.r1",
                official_heading="Ingresos",
                cells=(
                    FormCell(kind=FormCellKind.CASILLA, casilla_id="01"),
                    FormCell(kind=FormCellKind.DESIGN_CONSTANT, literal="00400"),
                ),
            ),
            FormGridRow(
                key="r2",
                heading_key="modelo.schema.130.form.test.r2",
                cells=(FormCell(kind=FormCellKind.CASILLA, casilla_id="02"), FormCell(kind=FormCellKind.BLANK)),
            ),
        ),
    )
    section_one = FormSectionDefinition(
        id="s1",
        heading_key="modelo.schema.130.form.test.s1",
        official_heading="I. Actividades económicas en estimación directa",
        blocks=(
            grid,
            *(FormFieldBlock(id=f"f{casilla}", casilla_id=casilla) for casilla in ("03", "04", "05", "06", "07")),
        ),
    )
    section_two = FormSectionDefinition(
        id="s2",
        heading_key="modelo.schema.130.form.test.s2",
        blocks=tuple(FormFieldBlock(id=f"f{casilla}", casilla_id=casilla) for casilla in _SECTION_TWO),
    )
    default_placements = (
        *(
            FormPlacementDefinition(casilla_id=casilla.id, kind=FormPlacementKind.ON_FORM, box_number=casilla.number)
            for casilla in snapshot.revision.casillas
            if str(casilla.id) not in {_WORKING, _UNPLACED}
        ),
        FormPlacementDefinition(casilla_id=_WORKING, kind=FormPlacementKind.WORKING_FIGURE),
        FormPlacementDefinition(
            casilla_id=_UNPLACED, kind=FormPlacementKind.UNPLACED, unplaced_reason=FormUnplacedReason.PENDING_REVIEW
        ),
    )
    return FormLayoutDefinition(
        id="m130-test",
        revision_id=snapshot.revision.id,
        seed_source=FormLayoutSeedSource.EXPORT_RECORD_DESIGN,
        generator_version=FORM_LAYOUT_GENERATOR_VERSION,
        source_state_digest="0" * 64,
        pages=(
            FormPageDefinition(
                id="p1",
                heading_key="modelo.schema.130.form.test.p1",
                official_ref="DR13001",
                sections=(section_one, section_two),
            ),
        ),
        placements=default_placements if placements is None else placements,
    )


def _form(
    snapshot: RegistrySnapshot,
    operation: PinnedAuthorityOperation,
    *,
    layout: FormLayoutDefinition | None = None,
    review: ModeloWorkReview | None = None,
    surface: tuple[ModeloEditPermittedSurfaceEntryV1, ...] | None = None,
    entered: frozenset[str] | None = None,
    language: OutputLanguage = OutputLanguage.EN,
) -> ModeloWorkForm:
    return build_modelo_work_form(
        review=review or _review(snapshot, operation),
        snapshot=snapshot,
        layout=layout,
        revision=None,
        permitted_surface=surface,
        entered_casilla_ids=entered,
        overridden_binding_ids=None,
        language=language,
    )


def _by_casilla(form: ModeloWorkForm) -> dict[str, ModeloFormField]:
    return {
        str(field.address.casilla_id): field
        for field in form.fields()
        if isinstance(field.address, ModeloFormCasillaAddressV1)
    }


def test_without_a_layout_every_casilla_is_listed_once_in_box_order(
    snapshot: RegistrySnapshot, operation: PinnedAuthorityOperation
) -> None:
    form = _form(snapshot, operation)

    boxes = [field.box for field in form.fields()]
    assert form.layout_provenance is ModeloFormLayoutProvenance.INSPECTION_ONLY
    assert form.inspection_reason is ModeloFormInspectionReason.LAYOUT_ABSENT
    assert len(boxes) == len(snapshot.revision.casillas)
    numbered = [int(box) for box in boxes if box is not None]
    assert numbered == sorted(numbered)
    assert boxes[-1] is None


def test_a_layout_for_another_revision_is_only_inspected(
    snapshot: RegistrySnapshot, operation: PinnedAuthorityOperation
) -> None:
    layout = _layout(snapshot).model_copy(update={"revision_id": "2000"})

    form = _form(snapshot, operation, layout=layout)

    assert form.inspection_reason is ModeloFormInspectionReason.LAYOUT_FOR_ANOTHER_REVISION


def test_a_declared_layout_accounts_for_every_casilla_exactly_once(
    snapshot: RegistrySnapshot, operation: PinnedAuthorityOperation
) -> None:
    form = _form(snapshot, operation, layout=_layout(snapshot))

    keys = [address_key(field.address) for field in form.fields()]
    assert form.layout_provenance is ModeloFormLayoutProvenance.GENERATED
    assert len(keys) == len(set(keys)) == len(snapshot.revision.casillas)
    assert [
        str(field.address.casilla_id)
        for field in form.working_figures
        if isinstance(field.address, ModeloFormCasillaAddressV1)
    ] == [_WORKING]
    assert [item.reason for item in form.unplaced] == [FormUnplacedReason.PENDING_REVIEW]


def test_a_layout_that_forgets_a_casilla_is_refused(
    snapshot: RegistrySnapshot, operation: PinnedAuthorityOperation
) -> None:
    complete = _layout(snapshot)
    forgetful = tuple(item for item in complete.placements if str(item.casilla_id) != _WORKING)

    with pytest.raises(ModeloWorkFormLayoutError, match="no placement"):
        _form(snapshot, operation, layout=_layout(snapshot, placements=forgetful))


def test_a_layout_that_shows_a_casilla_twice_is_refused(
    snapshot: RegistrySnapshot, operation: PinnedAuthorityOperation
) -> None:
    layout = _layout(snapshot)
    page = layout.pages[0]
    doubled = page.sections[1].model_copy(
        update={"blocks": (*page.sections[1].blocks, FormFieldBlock(id="again", casilla_id="08"))}
    )
    twice = layout.model_copy(update={"pages": (page.model_copy(update={"sections": (page.sections[0], doubled)}),)})

    with pytest.raises(ModeloWorkFormLayoutError, match="more than once"):
        _form(snapshot, operation, layout=twice)


def test_before_any_calculation_each_input_kind_reads_its_own_origin(
    snapshot: RegistrySnapshot, operation: PinnedAuthorityOperation
) -> None:
    fields = _by_casilla(_form(snapshot, operation, layout=_layout(snapshot)))

    assert fields["03"].origin is ModeloFormOrigin.NOT_CALCULATED_YET
    assert fields["01"].origin is ModeloFormOrigin.NOT_IMPORTED_YET
    assert fields["06"].origin is ModeloFormOrigin.NEEDS_INPUT
    assert fields["06"].required


def test_a_held_manual_value_is_entered_only_when_the_operator_recorded_it(
    snapshot: RegistrySnapshot, operation: PinnedAuthorityOperation
) -> None:
    review = _review(snapshot, operation)
    held = review.model_copy(
        update={
            "casillas": tuple(
                row.model_copy(update={"realised_kind": ModeloValueKind.LITERAL, "value": Decimal("0")})
                if str(row.casilla_id) in {"06", "08"}
                else row
                for row in review.casillas
            )
        }
    )

    unknown = _by_casilla(_form(snapshot, operation, layout=_layout(snapshot), review=held))
    recorded = _by_casilla(_form(snapshot, operation, layout=_layout(snapshot), review=held, entered=frozenset({"06"})))

    assert unknown["06"].origin is ModeloFormOrigin.DEFAULT_TO_CONFIRM
    assert recorded["06"].origin is ModeloFormOrigin.ENTERED
    assert recorded["08"].origin is ModeloFormOrigin.DEFAULT_TO_CONFIRM


def test_editability_follows_the_admission_and_the_source_policy(
    snapshot: RegistrySnapshot, operation: PinnedAuthorityOperation
) -> None:
    revision = snapshot.revision
    casilla = next(item for item in revision.casillas if item.id == "06")
    binding = next(item for item in revision.bindings if item.id == "modelo-130-pagos-fraccionados-anteriores")
    surface: tuple[ModeloEditPermittedSurfaceEntryV1, ...] = (
        ModeloEditWritableScalarSurfaceEntryV1(
            casilla_id="06",
            data_type=CasillaDataType.MONEY,
            allowed_intents=(ModeloEditScalarIntentKind.SET_TYPED_VALUE,),
            grammar=casilla_value_grammar(casilla),
        ),
        ModeloEditNonWritableScalarSurfaceEntryV1(
            casilla_id="08", reason=ModeloEditNonWritableReason.SCHEMA_DECLARED_READ_ONLY
        ),
        ModeloEditWritableBindingOverrideSurfaceEntryV1(
            binding_id="modelo-130-pagos-fraccionados-anteriores",
            allowed_intents=(ModeloEditBindingIntentKind.SET_OVERRIDE_VALUE,),
            grammar=binding_value_grammar(binding, revision=revision),
        ),
    )

    unadmitted = _by_casilla(_form(snapshot, operation, layout=_layout(snapshot)))
    admitted = _by_casilla(_form(snapshot, operation, layout=_layout(snapshot), surface=surface))

    assert unadmitted["06"].editability is ModeloFormEditability.NO_ADMISSION
    assert admitted["06"].editability is ModeloFormEditability.EDITABLE_VALUE
    assert admitted["08"].editability is ModeloFormEditability.NOT_WRITABLE
    assert admitted["08"].not_writable_reason == "schema_declared_read_only"
    assert admitted["01"].editability is ModeloFormEditability.LOCKED_SOURCE
    assert admitted["05"].editability is ModeloFormEditability.OVERRIDABLE_SOURCE
    assert admitted["03"].editability is ModeloFormEditability.CALCULATED


def test_labels_and_headings_say_which_language_served_them(
    snapshot: RegistrySnapshot, operation: PinnedAuthorityOperation
) -> None:
    form = _form(snapshot, operation, layout=_layout(snapshot), language=OutputLanguage.EN)
    fields = _by_casilla(form)
    section = form.pages[0].sections[0]

    assert fields["01"].label.disclosure is ModeloFormTextDisclosure.LOCALIZED
    assert fields["01"].label.text != snapshot.revision.casillas[0].label
    assert section.heading.disclosure is ModeloFormTextDisclosure.OFFICIAL_SPANISH
    assert form.pages[0].heading.disclosure is ModeloFormTextDisclosure.TECHNICAL


def test_grids_keep_official_rows_constants_and_blanks(
    snapshot: RegistrySnapshot, operation: PinnedAuthorityOperation
) -> None:
    form = _form(snapshot, operation, layout=_layout(snapshot))
    grid = form.pages[0].sections[0].blocks[0]

    assert isinstance(grid, ModeloFormGridBlock)
    assert [cell.kind for cell in grid.rows[0].cells] == [FormCellKind.CASILLA, FormCellKind.DESIGN_CONSTANT]
    assert grid.rows[0].cells[1].literal == "00400"
    assert grid.rows[1].cells[1].kind is FormCellKind.BLANK
    assert grid.rows[0].heading.text == "Ingresos"


def test_counts_roll_up_from_sections_to_the_form(
    snapshot: RegistrySnapshot, operation: PinnedAuthorityOperation
) -> None:
    form = _form(snapshot, operation, layout=_layout(snapshot))
    page = form.pages[0]

    assert page.counts.total == sum(section.counts.total for section in page.sections)
    assert form.counts.total == len(snapshot.revision.casillas)
    assert form.counts.needs_input == sum(1 for field in form.fields() if field.origin is ModeloFormOrigin.NEEDS_INPUT)
    assert form.counts.needs_input > 0
