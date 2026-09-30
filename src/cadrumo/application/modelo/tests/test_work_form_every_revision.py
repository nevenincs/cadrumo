"""Every revision a filer can open builds its editor form from its published layout.

The revisions are discovered in process from the pinned authority: every modelo
is asked, for every supported filing year and every accepted period code, which
revision governs that context, so the set is exactly the revisions the
workbench can open. Revisions only reachable outside the support envelope are
historical editions no filer can select and are not part of this population.

For each one the form must build without a layout refusal, from the generated
layout rather than the inspection-only fallback, and account for every casilla
of the revision exactly once: shown on a page, kept as a working figure, or
declared unplaced with its reason. No field is ever labelled with its own
identifier: a box the form gives no name says so in words.
"""

from __future__ import annotations

from collections import Counter

import pytest

from ....core.external_constants import OutputLanguage
from ....core.modelo_work_progress_state import ModeloWorkProgressState
from ....core.period import Period, accepted_filing_period_codes
from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ....domain.calculations.registry.errors import EjercicioOrdenNotYetPublishedError, NoRevisionForPeriodError
from ....domain.modelos.codes import ModeloCode
from ..work_form import build_modelo_work_form
from ..work_form_models import (
    ModeloFormBindingAddressV1,
    ModeloFormEditability,
    ModeloFormLayoutProvenance,
    ModeloFormOrigin,
    ModeloFormRepeatingBlock,
    ModeloFormTextDisclosure,
    ModeloWorkForm,
    address_key,
)
from ..work_form_service import modelo_form_snapshot
from ..work_review import ModeloWorkProgress, ModeloWorkReview, build_modelo_work_review_casillas

pytestmark = [pytest.mark.integration, pytest.mark.hex_application]


def _reachable_contexts(operation: PinnedAuthorityOperation) -> dict[tuple[str, str], tuple[int, str]]:
    """One filing context per revision the support envelope reaches.

    A context a modelo does not file in, or whose year's orden is not yet
    published, has no revision; any other refusal is a defect and propagates.
    """
    contexts: dict[tuple[str, str], tuple[int, str]] = {}
    for modelo in operation.modelo_ids():
        for year in operation.supported_filing_years().years:
            for code in accepted_filing_period_codes():
                try:
                    revision = operation.revision_for_context(modelo, filing_year=year, period=code)
                except (NoRevisionForPeriodError, EjercicioOrdenNotYetPublishedError):
                    continue
                contexts.setdefault((modelo, str(revision.id)), (year, code))
    return contexts


def _form(operation: PinnedAuthorityOperation, modelo: str, year: int, code: str) -> tuple[ModeloWorkForm, set[str]]:
    period = Period.from_year_and_code(year, code)
    snapshot = modelo_form_snapshot(
        operation,
        ModeloCode(modelo),
        year,
        period,
        str(operation.revision_for_context(modelo, filing_year=year, period=period.registry_token).id),
    )
    review = ModeloWorkReview(
        bucket_id="13000000-0000-4000-8000-000000000998",
        modelo=modelo,
        filing_year=year,
        period=period,
        registry_revision_id=snapshot.revision.id,
        work_unit_id="d" * 64,
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
        layout=operation.form_layout(modelo, snapshot.revision.id),
        revision=None,
        permitted_surface=None,
        entered_casilla_ids=frozenset(),
        overridden_binding_ids=frozenset(),
        language=OutputLanguage.ES,
    )
    return form, {str(casilla.id) for casilla in snapshot.revision.casillas}


def _shown_casillas(form: ModeloWorkForm) -> list[str]:
    """Every casilla a form accounts for: fields, repeating-group columns, working figures and unplaced boxes."""
    shown = [key[1] for key in (address_key(field.address) for field in form.fields()) if key[0] == "casilla"]
    for page in form.pages:
        for section in page.sections:
            for block in section.blocks:
                if isinstance(block, ModeloFormRepeatingBlock):
                    shown.extend(casilla for casilla in block.column_casilla_ids if casilla is not None)
    return shown


def test_every_reachable_revision_builds_its_form_and_accounts_for_every_casilla(
    operation: PinnedAuthorityOperation,
) -> None:
    contexts = _reachable_contexts(operation)
    assert contexts, "the support envelope reaches no revision, so this proves nothing"

    failures: list[str] = []
    for (modelo, revision_id), (year, code) in sorted(contexts.items()):
        form, declared = _form(operation, modelo, year, code)
        if form.layout_provenance is ModeloFormLayoutProvenance.INSPECTION_ONLY:
            failures.append(f"{modelo}/{revision_id}: no usable layout ({form.inspection_reason})")
            continue
        shown = Counter(_shown_casillas(form))
        repeated = sorted(casilla for casilla, count in shown.items() if count > 1)
        if repeated or set(shown) != declared:
            failures.append(
                f"{modelo}/{revision_id}: repeated {repeated[:5]}, missing {sorted(declared - set(shown))[:5]}, "
                f"invented {sorted(set(shown) - declared)[:5]}"
            )
    assert not failures, "\n".join(failures)


def test_a_box_the_design_fixes_is_shown_fixed_and_never_invents_its_figure(
    operation: PinnedAuthorityOperation,
) -> None:
    """Modelo 303's rate boxes are printed by the design, so they are shown, fixed, and never offered.

    The registry emits their literal as text without declaring its scale, so
    the form carries no number for them rather than the engine's own figure or
    the literal's raw digits, neither of which is what the filed fichero shows.
    """
    form, _declared = _form(operation, "303", 2026, "1T")
    rate = next(field for field in form.fields() if address_key(field.address) == ("casilla", "02"))

    assert rate.editability is ModeloFormEditability.DESIGN_CONSTANT
    assert rate.origin is ModeloFormOrigin.INFORMATIONAL
    assert rate.value is None


def test_no_field_of_any_reachable_revision_is_labelled_with_its_identifier(
    operation: PinnedAuthorityOperation,
) -> None:
    """A value the form gives no name reads as unnamed, in words, and keeps its identifier in its address."""
    labelled_by_id: list[str] = []
    unnamed = Counter[str]()
    for (modelo, revision_id), (year, code) in sorted(_reachable_contexts(operation).items()):
        form, _declared = _form(operation, modelo, year, code)
        for field in (*form.fields(), *form.working_figures, *(item.field for item in form.unplaced)):
            identifier = address_key(field.address)[1]
            if field.label.text == identifier or field.label.disclosure is ModeloFormTextDisclosure.TECHNICAL:
                labelled_by_id.append(f"{modelo}/{revision_id}: {identifier}")
            if field.label.disclosure is ModeloFormTextDisclosure.UNNAMED:
                unnamed[modelo] += 1
                assert field.label.text == "Casilla sin nombre", identifier

    assert not labelled_by_id, "\n".join(labelled_by_id[:20])
    assert unnamed["390"], "Modelo 390's first-page inputs have no name in the registry; pick another witness"


def test_modelo_390s_unnamed_first_page_inputs_keep_their_identifier_and_their_kind(
    operation: PinnedAuthorityOperation,
) -> None:
    form, _declared = _form(operation, "390", 2025, "0A")
    flag = next(
        field
        for field in form.fields()
        if field.address
        == ModeloFormBindingAddressV1(binding_id="modelo-390.page_1.sujeto-pasivo-registro-de-devolucion-mensual")
    )

    assert flag.label.disclosure is ModeloFormTextDisclosure.UNNAMED
    assert flag.label.text == "Casilla sin nombre"
    assert flag.data_type == "text", "the registry declares this input free text, and the form says the same"
