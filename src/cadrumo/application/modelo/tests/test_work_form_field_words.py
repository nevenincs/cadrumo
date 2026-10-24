"""The form says what a box offers and how its context and records read, so no frontend decides it.

Forms are built by the real builder over the published registry. A box the
filer replaced over a source offers going back to it, and one still showing
its source does not; an assumed value the filer may confirm carries the value
a confirmation stages, as an edit intent carries it. The Modelo 130 context
names its period in words, and a counterpart record of a Modelo 347 reads each
value as the table shows it, an empty value as nothing.
"""

from __future__ import annotations

from collections.abc import Callable
from decimal import Decimal

import pytest

from ....core.external_constants import OutputLanguage
from ....core.period import Period
from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ..edit_apply_scalar_contracts import wire_scalar_value
from ..source_policy import SourceOverridePolicy
from ..value_presentation import absent_value_text, format_casilla_value
from ..work_form_models import (
    ModeloFormContextFieldBlock,
    ModeloFormEditability,
    ModeloFormField,
    ModeloFormOrigin,
    ModeloFormRepeatingBlock,
    ModeloFormRepeatingRow,
    ModeloWorkForm,
    confirmable,
    revised_field,
)
from ..work_form_wording import period_words, worded_form
from .work_form_fixture import built_form

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_AMOUNT = Decimal("1234.50")


def _bound(form: ModeloWorkForm, *, policy: SourceOverridePolicy | None = None) -> ModeloFormField:
    return next(
        field
        for field in form.fields()
        if field.bindings and (policy is None or field.bindings[0].policy.override_policy is policy)
    )


def test_a_box_offers_going_back_to_its_source_only_while_the_filers_value_replaces_it(
    operation: PinnedAuthorityOperation,
) -> None:
    field = _bound(built_form(operation, "303", 2026, "1T"))

    replaced = revised_field(
        field, editability=ModeloFormEditability.OVERRIDABLE_SOURCE, origin=ModeloFormOrigin.OVERRIDES_SOURCE
    )
    sourced = revised_field(
        field, editability=ModeloFormEditability.OVERRIDABLE_SOURCE, origin=ModeloFormOrigin.IMPORTED
    )
    own_box = revised_field(field, editability=ModeloFormEditability.EDITABLE_VALUE, origin=ModeloFormOrigin.ENTERED)

    assert replaced.restorable and not sourced.restorable and not own_box.restorable
    with pytest.raises(ValueError, match="back to its source"):
        ModeloFormField.model_validate({**dict(sourced), "restorable": True})


def test_a_confirmable_box_carries_the_value_a_confirmation_stages(operation: PinnedAuthorityOperation) -> None:
    field = next(field for field in built_form(operation, "130", 2026, "1T").fields() if not field.bindings)

    assumed = revised_field(
        field,
        editability=ModeloFormEditability.EDITABLE_VALUE,
        origin=ModeloFormOrigin.DEFAULT_TO_CONFIRM,
        value=_AMOUNT,
    )
    entered = revised_field(assumed, origin=ModeloFormOrigin.ENTERED)

    assert confirmable(assumed)
    assert assumed.confirm_value == wire_scalar_value(_AMOUNT) == "1234.50"
    assert entered.confirm_value is None


@pytest.mark.parametrize("language", [OutputLanguage.EN, OutputLanguage.ES])
def test_the_context_names_its_period_in_words_and_an_absent_value_as_nothing(
    operation: PinnedAuthorityOperation, language: OutputLanguage
) -> None:
    form = built_form(operation, "130", 2026, "1T", language=language)

    context = {
        block.id: block
        for page in form.pages
        for section in page.sections
        for block in section.blocks
        if isinstance(block, ModeloFormContextFieldBlock)
    }

    assert context["periodo"].value == "1T"
    assert context["periodo"].value_text == period_words(Period.from_year_and_code(2026, "1T"), language)
    assert context["ejercicio"].value_text == "2026"
    assert context["nif"].value is None
    assert context["nif"].value_text == absent_value_text(language)


def _with_record(
    form: ModeloWorkForm, fill: Callable[[ModeloFormRepeatingBlock], ModeloFormRepeatingRow]
) -> ModeloWorkForm:
    pages = tuple(
        page.model_copy(
            update={
                "sections": tuple(
                    section.model_copy(
                        update={
                            "blocks": tuple(
                                block.model_copy(update={"rows": (fill(block),)})
                                if isinstance(block, ModeloFormRepeatingBlock)
                                else block
                                for block in section.blocks
                            )
                        }
                    )
                    for section in page.sections
                )
            }
        )
        for page in form.pages
    )
    return form.model_copy(update={"pages": pages})


def test_each_record_value_reads_as_the_table_shows_it(operation: PinnedAuthorityOperation) -> None:
    form = built_form(operation, "347", 2026, "0A", language=OutputLanguage.ES)

    def record(block: ModeloFormRepeatingBlock) -> ModeloFormRepeatingRow:
        values = tuple(_AMOUNT if data_type == "money" else None for data_type in block.column_data_types)
        return ModeloFormRepeatingRow(index=1, values=values)

    worded = worded_form(_with_record(form, record))
    blocks = [
        block
        for page in worded.pages
        for section in page.sections
        for block in section.blocks
        if isinstance(block, ModeloFormRepeatingBlock)
    ]

    assert blocks
    for block in blocks:
        (row,) = block.rows
        assert len(row.value_texts) == len(row.values)
        for value, text, data_type in zip(row.values, row.value_texts, block.column_data_types, strict=True):
            if value is None:
                assert text is None
            else:
                assert text == format_casilla_value(value, data_type=data_type, language=OutputLanguage.ES)
    assert any(text is not None for block in blocks for text in block.rows[0].value_texts)
    with pytest.raises(ValueError, match="align"):
        ModeloFormRepeatingRow(index=1, values=(None, None), value_texts=("x",))


def test_a_box_holds_the_filers_own_value_when_typed_here_or_replacing_its_source(
    operation: PinnedAuthorityOperation,
) -> None:
    field = _bound(built_form(operation, "303", 2026, "1T"))

    own = {
        origin: revised_field(field, origin=origin).filers_own
        for origin in (
            ModeloFormOrigin.ENTERED,
            ModeloFormOrigin.OVERRIDES_SOURCE,
            ModeloFormOrigin.IMPORTED,
            ModeloFormOrigin.DEFAULT_TO_CONFIRM,
            ModeloFormOrigin.CALCULATED,
        )
    }

    assert own == {
        ModeloFormOrigin.ENTERED: True,
        ModeloFormOrigin.OVERRIDES_SOURCE: True,
        ModeloFormOrigin.IMPORTED: False,
        ModeloFormOrigin.DEFAULT_TO_CONFIRM: False,
        ModeloFormOrigin.CALCULATED: False,
    }
    with pytest.raises(ValueError, match="own value"):
        ModeloFormField.model_validate(
            {**dict(revised_field(field, origin=ModeloFormOrigin.IMPORTED)), "filers_own": True}
        )
