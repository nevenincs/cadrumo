"""The form says what frontends would otherwise choose: page applicability, a fixed figure, the modelo's name.

Every form is built by the real builder over the published registry. A page
that does not apply says so in the words for the period's kind, a box the
design fixes shows a figure it holds, the filed wording follows the recorded
closure itself, and a box's stored standing always fits its own origin and
blockers.
"""

from __future__ import annotations

from decimal import Decimal

import pytest
from pydantic import ValidationError

from ....core.casilla_id import validated_casilla_id
from ....core.external_constants import OutputLanguage
from ....core.i18n.render import tr
from ....core.period import Period
from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ..value_presentation import format_casilla_value
from ..work_form_models import (
    ModeloFormCasillaAddressV1,
    ModeloFormEditability,
    ModeloFormEditClosure,
    ModeloFormField,
    ModeloFormOrigin,
    ModeloFormStanding,
    ModeloFormText,
    ModeloFormTextDisclosure,
    revised_field,
)
from ..work_form_wording import does_not_apply_words, field_value_text, origin_words, worded_form
from .work_form_fixture import built_form

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_EN = OutputLanguage.EN
_FORMS = (("303", 2026, "1T"), ("303", 2026, "4T"), ("130", 2026, "1T"), ("111", 2026, "1T"), ("390", 2025, "0A"))


def _field(**update: object) -> ModeloFormField:
    data: dict[str, object] = {
        "address": ModeloFormCasillaAddressV1(casilla_id=validated_casilla_id("01")),
        "box": "01",
        "label": ModeloFormText(text="Box", disclosure=ModeloFormTextDisclosure.LOCALIZED),
        "help": None,
        "data_type": "money",
        "value": None,
        "origin": ModeloFormOrigin.NEEDS_INPUT,
        "editability": ModeloFormEditability.EDITABLE_VALUE,
        "required": True,
    }
    data.update(update)
    return ModeloFormField.model_validate(data)


def test_a_page_that_does_not_apply_says_so_for_its_period_and_one_that_applies_says_nothing(
    operation: PinnedAuthorityOperation,
) -> None:
    worded = 0
    for modelo, year, code in _FORMS:
        form = built_form(operation, modelo, year, code, entered=frozenset())
        expected = does_not_apply_words(form.period, _EN)
        for page in form.pages:
            assert page.applicability_words == (expected if page.applies is False else None), (modelo, page.id)
            worded += page.applies is False
    assert worded, "some real page does not apply in the periods built"
    assert does_not_apply_words(Period.from_year_and_code(2026, "1T"), _EN) == tr(
        "workspace.modelo.applicability.quarter", locale="en"
    )
    assert does_not_apply_words(Period.from_year_and_code(2025, "0A"), _EN) == tr(
        "workspace.modelo.applicability.year", locale="en"
    )


def test_the_form_names_the_modelo_apart_from_its_number(operation: PinnedAuthorityOperation) -> None:
    form = built_form(operation, "130", 2026, "1T", entered=frozenset())

    assert form.modelo_name is not None and "130" not in form.modelo_name
    assert form.modelo_title == tr("workspace.modelo.modelo_title", modelo="130", title=form.modelo_name, locale="en")
    assert form.modelo_number == tr("workspace.modelo.modelo_number", modelo="130", locale="en")


def test_a_box_the_design_fixes_shows_a_figure_it_holds_and_none_when_it_holds_nothing() -> None:
    fixed = _field(
        editability=ModeloFormEditability.DESIGN_CONSTANT,
        origin=ModeloFormOrigin.INFORMATIONAL,
        value=Decimal("1500.00"),
        required=False,
    )

    shown = field_value_text(fixed, _EN)
    assert shown == format_casilla_value(Decimal("1500.00"), data_type="money", language=_EN)
    assert shown is not None and "1,500.00" in shown
    assert field_value_text(revised_field(fixed, value=None), _EN) is None


def test_the_filed_wording_follows_the_recorded_closure(operation: PinnedAuthorityOperation) -> None:
    form = built_form(operation, "210", 2025, "0A", entered=frozenset())
    asking = next(field for field in form.fields() if field.origin is ModeloFormOrigin.NEEDS_INPUT)

    closed = worded_form(
        form.model_copy(update={"edit_closure": ModeloFormEditClosure.RECORDED_AS_FILED, "edit_admitted": False})
    )
    closed_field = next(field for field in closed.fields() if field.address == asking.address)

    assert asking.origin_words == origin_words(asking, language=_EN)
    assert closed_field.origin_words == origin_words(asking, recorded=True, language=_EN)
    assert closed_field.origin_words != asking.origin_words


def test_a_stored_standing_always_fits_the_boxs_own_origin_and_blockers() -> None:
    waiting = _field(origin=ModeloFormOrigin.NOT_CALCULATED_YET, editability=ModeloFormEditability.CALCULATED)
    assert waiting.standing is ModeloFormStanding.WAITING

    with pytest.raises(ValidationError, match="standing"):
        _field(origin=ModeloFormOrigin.CALCULATED, standing=ModeloFormStanding.NEEDS_YOU)
    # A copy that settles the box takes the standing its new origin gives, never the one it waited with.
    settled = revised_field(waiting, origin=ModeloFormOrigin.CALCULATED, value=Decimal("10"))
    assert settled.standing is ModeloFormStanding.DONE
    # A standing the builder gave for the declaration or page is kept while the box still allows it.
    set_aside = revised_field(_field(), standing=ModeloFormStanding.DONE)
    assert revised_field(set_aside, value=None).standing is ModeloFormStanding.DONE
