"""A field serves the rank it sorts by when a page is ordered by attention, decided from its origin and blockers."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ..work_form_field_vocabulary import (
    BLOCKED_ATTENTION_RANK,
    SETTLED_ATTENTION_RANK,
    ModeloFormBlocker,
    ModeloFormOrigin,
    field_attention_rank,
)
from ..work_form_models import ModeloFormField, revised_field, section_fields
from .work_form_fixture import built_form

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_ORIGIN = ModeloFormOrigin
_BLOCKER = ModeloFormBlocker(code="blocking_rule")


def test_a_blocked_box_comes_first_whatever_its_origin() -> None:
    assert {field_attention_rank(origin, (_BLOCKER,)) for origin in ModeloFormOrigin} == {BLOCKED_ATTENTION_RANK}


def test_the_unblocked_order_is_value_needed_then_confirm_then_import_then_settled() -> None:
    needed = field_attention_rank(_ORIGIN.NEEDS_INPUT)

    assert field_attention_rank(_ORIGIN.CALCULATION_FAILED) == needed
    assert (
        BLOCKED_ATTENTION_RANK
        < needed
        < field_attention_rank(_ORIGIN.DEFAULT_TO_CONFIRM)
        < field_attention_rank(_ORIGIN.NOT_IMPORTED_YET)
        < SETTLED_ATTENTION_RANK
    )
    settled = set(ModeloFormOrigin) - {
        _ORIGIN.NEEDS_INPUT,
        _ORIGIN.CALCULATION_FAILED,
        _ORIGIN.DEFAULT_TO_CONFIRM,
        _ORIGIN.NOT_IMPORTED_YET,
    }
    assert {field_attention_rank(origin) for origin in settled} == {SETTLED_ATTENTION_RANK}


def _fields(operation: PinnedAuthorityOperation) -> tuple[ModeloFormField, ...]:
    form = built_form(operation, "349", operation.supported_filing_years().horizon, "1T")
    return tuple(field for page in form.pages for section in page.sections for field in section_fields(section))


def test_every_served_field_carries_the_rank_its_origin_and_blockers_give(
    authority_operation: PinnedAuthorityOperation,
) -> None:
    fields = _fields(authority_operation)

    assert fields
    assert all(field.attention_rank == field_attention_rank(field.origin, field.blockers) for field in fields)


def test_a_revised_field_ranks_by_its_new_origin_and_a_rank_it_does_not_have_is_refused(
    authority_operation: PinnedAuthorityOperation,
) -> None:
    field = _fields(authority_operation)[0]

    assert revised_field(field, blockers=(_BLOCKER,)).attention_rank == BLOCKED_ATTENTION_RANK
    wrong = (field.attention_rank + 1) % (SETTLED_ATTENTION_RANK + 1)
    with pytest.raises(ValidationError, match="attention rank"):
        ModeloFormField.model_validate(field.model_dump() | {"attention_rank": wrong})
