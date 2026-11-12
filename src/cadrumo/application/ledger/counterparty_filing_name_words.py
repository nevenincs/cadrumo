"""The words a surface shows for a counterparty's filing name, served in the worker's language.

A surface renders these words and authors none: each state a slot can be in,
each party kind and each name part has one catalogue entry, and a value the
catalogue has no entry for is refused here rather than shown as its token.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from ...core.external_constants import OutputLanguage
from ...core.i18n.render import tr
from ...core.models import STRICT_FROZEN_HIDDEN_INPUT_CONFIG
from ...domain.filing.declared_party_name import DeclaredPartyKind
from ..operations.error_detail import MAX_OPERATION_ERROR_WORDS_LENGTH, served_words_language

FilingNameSlotRefusal = Literal["missing", "single_surname", "too_wide"]
FilingNamePart = Literal["primer_apellido", "segundo_apellido", "nombre", "razon_social"]
FilingNameSlotState = Literal["fits", "fits_by_rendering", "missing", "single_surname", "too_wide"]
"""What a slot is in for the stated name: filed whole, filed by a rendering, or the export's refusal."""

_SLOT_STATE_KEYS: dict[FilingNameSlotState, str] = {
    "fits": "application.ledger.counterparty.served.slot_state.fits",
    "fits_by_rendering": "application.ledger.counterparty.served.slot_state.fits_by_rendering",
    "missing": "application.ledger.counterparty.served.slot_state.missing",
    "single_surname": "application.ledger.counterparty.served.slot_state.single_surname",
    "too_wide": "application.ledger.counterparty.served.slot_state.too_wide",
}
_PARTY_KIND_KEYS: dict[DeclaredPartyKind, str] = {
    DeclaredPartyKind.NATURAL_PERSON: "application.ledger.counterparty.served.party_kind.natural_person",
    DeclaredPartyKind.ENTITY: "application.ledger.counterparty.served.party_kind.entity",
}
_PART_KEYS: dict[FilingNamePart, str] = {
    "primer_apellido": "application.ledger.counterparty.served.part.primer_apellido",
    "segundo_apellido": "application.ledger.counterparty.served.part.segundo_apellido",
    "nombre": "application.ledger.counterparty.served.part.nombre",
    "razon_social": "application.ledger.counterparty.served.part.razon_social",
}


def slot_state(*, fits: bool, refusal: FilingNameSlotRefusal | None, uses_rendering: bool) -> FilingNameSlotState:
    """The one state a slot is in, from the export's own answer for it."""
    if refusal is not None:
        return refusal
    if not fits:
        raise ValueError("a slot that does not fit carries the export's refusal")
    return "fits_by_rendering" if uses_rendering else "fits"


def slot_state_words(state: FilingNameSlotState, language: OutputLanguage) -> str:
    """The sentence for a slot's state."""
    return tr(_SLOT_STATE_KEYS[state], locale=language.value)


def kind_words(kind: str, language: OutputLanguage) -> str:
    """The label for a party kind, refusing a kind the domain does not declare."""
    return tr(_PARTY_KIND_KEYS[DeclaredPartyKind(kind)], locale=language.value)


def name_part_words(part: FilingNamePart, language: OutputLanguage) -> str:
    """The label for a name part."""
    return tr(_PART_KEYS[part], locale=language.value)


class CounterpartyPartyKindChoice(BaseModel):
    """One party kind a filing name can be stated for, with its served label."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    kind: DeclaredPartyKind
    words: str = Field(min_length=1, max_length=MAX_OPERATION_ERROR_WORDS_LENGTH)
    words_language: OutputLanguage


def party_kind_choices() -> tuple[CounterpartyPartyKindChoice, ...]:
    """Every declared party kind in declaration order, labelled in the worker's language."""
    language = served_words_language()
    return tuple(
        CounterpartyPartyKindChoice(kind=kind, words=kind_words(kind.value, language), words_language=language)
        for kind in DeclaredPartyKind
    )


__all__ = [
    "CounterpartyPartyKindChoice",
    "FilingNamePart",
    "FilingNameSlotRefusal",
    "FilingNameSlotState",
    "kind_words",
    "name_part_words",
    "party_kind_choices",
    "slot_state",
    "slot_state_words",
]
