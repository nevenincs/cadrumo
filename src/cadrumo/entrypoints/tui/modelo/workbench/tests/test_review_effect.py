"""The review says what a change replaces, naming the place a replaced value came from.

Changes are staged through the real edit session, so what each one displaces is
decided the way the workbench decides it. Expected wording is written by hand.
"""

from __future__ import annotations

from decimal import Decimal

import pytest
from textual.widgets import Static

from ......application.modelo.source_policy import SourceFamily
from ......application.modelo.work_form_models import (
    ModeloFormCasillaAddressV1,
    ModeloFormEarlierFiling,
    ModeloFormEditability,
    ModeloFormField,
    ModeloFormOrigin,
    ModeloFormText,
    ModeloFormTextDisclosure,
    ModeloFormValueSource,
)
from ......core.config import override_settings
from ......core.external_constants import OutputLanguage
from ......core.i18n.render import lookup_translation
from ......core.period import Period
from ....components.host import ScreenHostApp
from ..review import REVIEW_EFFECTS, EditReviewScreen, ReviewDecision, change_line
from ..session import StagedChange, WorkbenchEditSession

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_LANGUAGES = tuple(OutputLanguage)


def _field(
    origin: ModeloFormOrigin,
    source: ModeloFormValueSource | None,
    *,
    editability: ModeloFormEditability = ModeloFormEditability.OVERRIDABLE_SOURCE,
) -> ModeloFormField:
    return ModeloFormField(
        address=ModeloFormCasillaAddressV1(casilla_id="05"),
        box="05",
        label=ModeloFormText(text="Carried amount", disclosure=ModeloFormTextDisclosure.LOCALIZED),
        help=None,
        data_type="money",
        value=Decimal("500"),
        origin=origin,
        editability=editability,
        required=False,
        source=source,
    )


def _staged(field: ModeloFormField, language: OutputLanguage = OutputLanguage.EN) -> StagedChange:
    session = WorkbenchEditSession(language)
    assert session.stage_value(field, Decimal("600"), "600.00 €") is None
    (change,) = session.changes
    return change


def _earlier(*periods: Period) -> ModeloFormValueSource:
    return ModeloFormValueSource(
        family=SourceFamily.EARLIER_FILINGS,
        earlier_filings=tuple(ModeloFormEarlierFiling(modelo="130", period=period) for period in periods),
    )


def _effect(line: str) -> str:
    return line.rsplit("(", 1)[1].rstrip(")")


def test_a_replaced_value_names_the_place_it_came_from() -> None:
    q4 = Period.from_year_and_code(2025, "4T")
    q3 = Period.from_year_and_code(2025, "3T")
    imported = ModeloFormOrigin.IMPORTED

    with override_settings(cadrumo_output_language="en"):
        records = _staged(_field(imported, ModeloFormValueSource(family=SourceFamily.RECORDS)))
        carried = _staged(_field(imported, _earlier(q4)))
        two_carried = _staged(_field(imported, _earlier(q3, q4)))
        profile = _staged(_field(ModeloFormOrigin.OVERRIDES_SOURCE, ModeloFormValueSource(family=SourceFamily.PROFILE)))
        calculated = _staged(
            _field(ModeloFormOrigin.CALCULATED, None, editability=ModeloFormEditability.EDITABLE_OVERRIDE)
        )
        unnamed = _staged(_field(imported, None))

        assert _effect(change_line(records)) == "replaces the value from your records"
        assert _effect(change_line(carried)) == "replaces the value from modelo 130, 4th quarter 2025"
        assert _effect(change_line(two_carried)) == "replaces the value from an earlier declaration"
        assert _effect(change_line(profile)) == "replaces the value from your profile"
        assert _effect(change_line(calculated)) == "replaces the calculated value"
        assert _effect(change_line(unnamed)) == "replaces the value from its source"
    with override_settings(cadrumo_output_language="es"):
        carried_es = _staged(_field(imported, _earlier(q4)), OutputLanguage.ES)
        assert _effect(change_line(carried_es)) == "sustituye el valor del modelo 130, 4.º trimestre 2025"


@pytest.mark.parametrize("language", _LANGUAGES, ids=[item.value for item in _LANGUAGES])
def test_no_effect_calls_a_value_imported(language: OutputLanguage) -> None:
    imported_words = {"en": "imported", "es": "importado", "ca": "importat", "hu": "importált"}[language.value]
    for effect in REVIEW_EFFECTS:
        text = lookup_translation(f"tui.modelo.workbench.review.effect.{effect}", locale=language.value)
        assert text, effect
        assert imported_words not in text, effect


async def _review_lines(screen: EditReviewScreen) -> list[str]:
    app: ScreenHostApp[ReviewDecision] = ScreenHostApp(screen)
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.pause()
        return [str(item.render()) for item in screen.query(Static) if item.id is not None]


@pytest.mark.asyncio
async def test_the_review_opens_with_the_declarations_result_line_when_given() -> None:
    with override_settings(cadrumo_output_language="en"):
        change = _staged(_field(ModeloFormOrigin.IMPORTED, ModeloFormValueSource(family=SourceFamily.RECORDS)))
        status = "Result to pay 120.00 € · to confirm: 2"
        with_status = await _review_lines(EditReviewScreen((change,), status_line=status))
        without = await _review_lines(EditReviewScreen((change,)))

    assert with_status[0] == status
    assert with_status[1:] == without
    assert status not in without
