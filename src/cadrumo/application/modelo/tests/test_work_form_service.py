"""The change query lists what moved between two reads of one declaration's form.

Driven over forms the real builder produces from the compiled Modelo 130
registry: an unchanged read reports nothing, a value or origin that moved is
reported with both readings, and a box the later read no longer shows is
reported as gone rather than dropped.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from ....core.external_constants import OutputLanguage
from ....core.modelo_work_progress_state import ModeloWorkProgressState
from ....core.period import Period
from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ....domain.calculations.registry.schema import RegistrySnapshot
from ....domain.filing.schema import ModeloValueKind
from ..work_form import build_modelo_work_form
from ..work_form_models import ModeloFormOrigin, ModeloWorkForm
from ..work_form_service import modelo_work_form_changes
from ..work_review import ModeloWorkProgress, ModeloWorkReview, build_modelo_work_review_casillas

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_MODELO = "130"
_YEAR = 2026
_PERIOD = "1T"


@pytest.fixture
def snapshot(operation: PinnedAuthorityOperation) -> RegistrySnapshot:
    return operation.snapshot(_MODELO, filing_year=_YEAR, period=_PERIOD)


def _review(snapshot: RegistrySnapshot, operation: PinnedAuthorityOperation) -> ModeloWorkReview:
    return ModeloWorkReview(
        bucket_id="13000000-0000-4000-8000-000000000452",
        modelo=_MODELO,
        filing_year=_YEAR,
        period=Period.from_year_and_code(_YEAR, _PERIOD),
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


def _form(review: ModeloWorkReview, snapshot: RegistrySnapshot, *, entered: frozenset[str]) -> ModeloWorkForm:
    return build_modelo_work_form(
        review=review,
        snapshot=snapshot,
        layout=None,
        revision=None,
        permitted_surface=None,
        entered_casilla_ids=entered,
        overridden_binding_ids=frozenset(),
        language=OutputLanguage.EN,
    )


def _with_value(review: ModeloWorkReview, casilla_id: str, value: Decimal) -> ModeloWorkReview:
    casillas = tuple(
        row.model_copy(update={"value": value, "realised_kind": ModeloValueKind.LITERAL})
        if row.casilla_id == casilla_id
        else row
        for row in review.casillas
    )
    return review.model_copy(update={"casillas": casillas})


def test_an_unchanged_read_reports_nothing(snapshot: RegistrySnapshot, operation: PinnedAuthorityOperation) -> None:
    review = _review(snapshot, operation)

    assert (
        modelo_work_form_changes(
            _form(review, snapshot, entered=frozenset()), _form(review, snapshot, entered=frozenset())
        )
        == ()
    )


def test_a_moved_value_is_reported_with_both_readings_and_origins(
    snapshot: RegistrySnapshot, operation: PinnedAuthorityOperation
) -> None:
    review = _review(snapshot, operation)
    before = _form(review, snapshot, entered=frozenset())
    after = _form(_with_value(review, "06", Decimal("100")), snapshot, entered=frozenset({"06"}))

    changes = modelo_work_form_changes(before, after)

    assert [change.box for change in changes] == ["06"]
    (change,) = changes
    assert change.before is None
    assert change.after == Decimal("100")
    assert change.before_origin is not ModeloFormOrigin.ENTERED
    assert change.after_origin is ModeloFormOrigin.ENTERED


def test_a_box_the_later_read_no_longer_shows_is_reported_as_gone(
    snapshot: RegistrySnapshot, operation: PinnedAuthorityOperation
) -> None:
    review = _review(snapshot, operation)
    shown = _with_value(review, "06", Decimal("100"))
    hidden = shown.model_copy(update={"casillas": tuple(row for row in shown.casillas if row.casilla_id != "06")})

    changes = modelo_work_form_changes(
        _form(shown, snapshot, entered=frozenset({"06"})), _form(hidden, snapshot, entered=frozenset())
    )

    gone = [change for change in changes if change.box == "06"]
    assert len(gone) == 1
    assert gone[0].before == Decimal("100")
    assert gone[0].after is None
    assert gone[0].after_origin is None
