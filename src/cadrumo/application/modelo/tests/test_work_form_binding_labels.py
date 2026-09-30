"""An input no box owns is named after the one box it feeds, and says it is unnamed otherwise.

Built by the real read model over the published authority. Modelo 100's
direct-estimation choice feeds exactly one numbered box, so it reads as
additional data for that box in every language; Modelo 390's header inputs
feed no box at all, so they keep the plain words for a box without a name and
never their identifiers.
"""

from __future__ import annotations

import pytest

from ....core.external_constants import OutputLanguage
from ....core.modelo_work_progress_state import ModeloWorkProgressState
from ....core.period import Period
from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ....domain.modelos.codes import ModeloCode
from ..work_form import build_modelo_work_form
from ..work_form_models import ModeloFormBindingAddressV1, ModeloFormField, ModeloFormTextDisclosure, ModeloWorkForm
from ..work_form_service import modelo_form_snapshot
from ..work_review import ModeloWorkProgress, ModeloWorkReview, build_modelo_work_review_casillas

pytestmark = [pytest.mark.integration, pytest.mark.hex_application]

_DIRECT_ESTIMATION = "renta-modelo-100-estimacion-directa-es-normal"


def _form(
    operation: PinnedAuthorityOperation, modelo: str, year: int, code: str, language: OutputLanguage
) -> ModeloWorkForm:
    period = Period.from_year_and_code(year, code)
    revision_id = str(operation.revision_for_context(modelo, filing_year=year, period=code).id)
    snapshot = modelo_form_snapshot(operation, ModeloCode(modelo), year, period, revision_id)
    review = ModeloWorkReview(
        bucket_id="13000000-0000-4000-8000-000000000224",
        modelo=modelo,
        filing_year=year,
        period=period,
        registry_revision_id=snapshot.revision.id,
        work_unit_id="b" * 64,
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
        layout=operation.form_layout(modelo, snapshot.revision.id),
        revision=None,
        permitted_surface=None,
        entered_casilla_ids=None,
        overridden_binding_ids=None,
        language=language,
    )


def _binding_fields(form: ModeloWorkForm) -> list[ModeloFormField]:
    return [field for field in form.fields() if isinstance(field.address, ModeloFormBindingAddressV1)]


@pytest.mark.parametrize(
    ("language", "expected"),
    [
        (OutputLanguage.EN, "Additional data for box 0224"),
        (OutputLanguage.ES, "Dato adicional de la casilla 0224"),
        (OutputLanguage.CA, "Dada addicional de la casella 0224"),
        (OutputLanguage.HU, "Kiegészítő adat a(z) 0224. rovathoz"),
    ],
)
def test_an_input_that_feeds_one_box_is_named_after_that_box(
    operation: PinnedAuthorityOperation, language: OutputLanguage, expected: str
) -> None:
    form = _form(operation, "100", 2024, "0A", language)
    field = next(
        field
        for field in _binding_fields(form)
        if isinstance(field.address, ModeloFormBindingAddressV1) and str(field.address.binding_id) == _DIRECT_ESTIMATION
    )

    assert field.label.text == expected
    assert field.label.disclosure is ModeloFormTextDisclosure.LOCALIZED


def test_an_input_that_feeds_no_box_says_it_has_no_name_and_never_shows_its_identifier(
    operation: PinnedAuthorityOperation,
) -> None:
    form = _form(operation, "390", 2025, "0A", OutputLanguage.EN)
    unnamed = [field for field in _binding_fields(form) if field.label.disclosure is ModeloFormTextDisclosure.UNNAMED]

    assert unnamed, "Modelo 390 declares header inputs that feed no box"
    assert {field.label.text for field in unnamed} == {"Unnamed box"}
    assert not any(
        str(field.address.binding_id) in field.label.text
        for field in unnamed
        if isinstance(field.address, ModeloFormBindingAddressV1)
    )
