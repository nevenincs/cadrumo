"""A counterparty's filing-name view serves the words for every state, kind and part, in every language.

A surface renders these words and authors none. Each enumerated value has a
finished label in each supported locale, and the words follow the worker's
language.
"""

from __future__ import annotations

import re
from typing import get_args

import pytest

from cadrumo.core.config import override_settings
from cadrumo.core.external_constants import OutputLanguage
from cadrumo.core.i18n.render import tr

from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ....domain.filing.declared_party_name import (
    DeclaredPartyFilingName,
    DeclaredPartyKind,
    DeclaredPartyNameRendering,
)
from ..counterparty_establishment import ConfirmedCounterpartyFacts
from ..counterparty_filing_name_slots import counterparty_filing_name_slots
from ..counterparty_filing_name_words import (
    FilingNamePart,
    FilingNameSlotRefusal,
    FilingNameSlotState,
    kind_words,
    name_part_words,
    party_kind_choices,
    slot_state,
    slot_state_words,
)
from ..counterparty_operation import CounterpartyFilingNameProjection

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_UNRENDERED = re.compile(r"\bapplication\.|\{|\}|%\(|%\{")


def _entity(length: int, *, renderings: tuple[DeclaredPartyNameRendering, ...] = ()) -> DeclaredPartyFilingName:
    return DeclaredPartyFilingName(kind=DeclaredPartyKind.ENTITY, razon_social="F" * length, renderings=renderings)


@pytest.mark.parametrize("language", list(OutputLanguage))
def test_every_state_kind_and_part_has_finished_words_in_every_language(language: OutputLanguage) -> None:
    states = get_args(FilingNameSlotState)
    parts = get_args(FilingNamePart)
    assert set(states) == {"fits", "fits_by_rendering", "missing", "single_surname", "too_wide"}

    words = [slot_state_words(state, language) for state in states]
    words += [name_part_words(part, language) for part in parts]
    words += [kind_words(kind.value, language) for kind in DeclaredPartyKind]

    assert all(text.strip() for text in words)
    assert not any(_UNRENDERED.search(text) for text in words)
    assert len(set(words)) == len(words)
    if language is not OutputLanguage.EN:
        english = [slot_state_words(state, OutputLanguage.EN) for state in states]
        assert not set(english) & set(words)


def test_a_slot_state_is_the_exports_own_answer() -> None:
    assert slot_state(fits=True, refusal=None, uses_rendering=False) == "fits"
    assert slot_state(fits=True, refusal=None, uses_rendering=True) == "fits_by_rendering"
    refusals: tuple[FilingNameSlotRefusal, ...] = ("missing", "single_surname", "too_wide")
    for refusal in refusals:
        assert slot_state(fits=False, refusal=refusal, uses_rendering=False) == refusal
    with pytest.raises(ValueError):
        slot_state(fits=False, refusal=None, uses_rendering=False)


@pytest.mark.parametrize("language", list(OutputLanguage))
def test_the_view_serves_each_slot_state_and_part_limit_in_the_workers_language(
    language: OutputLanguage, operation: PinnedAuthorityOperation
) -> None:
    with override_settings(cadrumo_output_language=language.value):
        unstated, limits = counterparty_filing_name_slots(operation, None)
        widths = sorted({slot.width for slot in unstated})
        widest = widths[-1]
        whole, _ = counterparty_filing_name_slots(operation, _entity(1))
        too_wide, _ = counterparty_filing_name_slots(operation, _entity(widest + 1))
        rendered, _ = counterparty_filing_name_slots(
            operation,
            _entity(
                widest + 1,
                renderings=tuple(DeclaredPartyNameRendering(width=width, text="R" * width) for width in widths),
            ),
        )

    for slots, state in (
        (unstated, "missing"),
        (whole, "fits"),
        (too_wide, "too_wide"),
        (rendered, "fits_by_rendering"),
    ):
        assert slots
        assert {slot.state for slot in slots} == {state}
        assert {slot.state_words for slot in slots} == {
            tr(f"application.ledger.counterparty.served.slot_state.{state}", locale=language.value)
        }
        assert {slot.edition_words_language for slot in slots} == {language}
    assert {limit.part for limit in limits} <= set(get_args(FilingNamePart))
    for limit in limits:
        assert limit.part_words == name_part_words(limit.part, language)
        assert limit.words_language is language


@pytest.mark.parametrize("language", list(OutputLanguage))
def test_the_stated_name_and_the_kind_choices_serve_the_kind_words(language: OutputLanguage) -> None:
    with override_settings(cadrumo_output_language=language.value):
        choices = party_kind_choices()
        fact = ConfirmedCounterpartyFacts.create(
            tax_identifier="B00015016", asserted_by="operator", declared_filing_name=_entity(10)
        )
        projection = CounterpartyFilingNameProjection.from_fact(fact)

    assert [choice.kind for choice in choices] == list(DeclaredPartyKind)
    assert all(choice.words_language is language for choice in choices)
    assert {choice.words for choice in choices} == {kind_words(kind.value, language) for kind in DeclaredPartyKind}
    assert projection is not None
    assert projection.party_kind_words == kind_words("entity", language)
    assert projection.party_kind_words_language is language
