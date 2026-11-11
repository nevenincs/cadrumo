"""Hold each reviewed party-name rule to the design text that states it.

A semantic-map entry may carry a :class:`~.semantic_map.SemanticMapPartyName`:
the composition a design prescribes for a party-name slot, with the design's
own sentences quoted. This check runs where the map meets the parsed design,
so each quotation is found in the exact text of the slot it is stated on, and
the declared composition is held to it: the natural-person parts must appear in
the quoted sentence in the declared order, the separator must be the one the
sentence names, and the entity sentence must ask for the razón social.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Final

from cadrumo.domain.calculations.registry.errors import RegistryValidationError
from cadrumo.domain.calculations.registry.party_name_composition import PartyNameComponent

from .record_design_intermediate import AnchorKey, RecordDesignIntermediate, intermediate_anchor_key
from .semantic_map import SemanticMap, SemanticMapEntry, SemanticMapPartyName, semantic_anchor_key

#: How the designs name each part in the sentence that orders them.
_COMPONENT_WORDS: Final[Mapping[PartyNameComponent, str]] = {
    PartyNameComponent.PRIMER_APELLIDO: "primer apellido",
    PartyNameComponent.SEGUNDO_APELLIDO: "segundo apellido",
    PartyNameComponent.NOMBRE: "nombre",
    PartyNameComponent.RAZON_SOCIAL: "razón social",
}

#: How the designs name a separator between two parts.
_SEPARATOR_WORDS: Final[Mapping[str, str]] = {" ": "un espacio"}

_WHITESPACE: Final = re.compile(r"\s+")


def verify_party_name_statements(semantic_map: SemanticMap, intermediate: RecordDesignIntermediate) -> None:
    """Refuse a party-name rule its design text does not state, or states differently.

    Raises:
        RegistryValidationError: A quotation is absent from its slot, a referred
            slot is not in the design, or the declared order, separator or
            entity part disagrees with the quoted sentence.
    """
    contents: dict[AnchorKey, str] = {
        intermediate_anchor_key(field): _collapsed(field.content or "")
        for sheet in intermediate.sheets
        for field in sheet.fields
    }
    for entry in semantic_map.entries:
        rule = entry.party_name
        if rule is None:
            continue
        own_text = _slot_text(contents, semantic_anchor_key(entry.anchor), entry)
        stating_text = own_text
        if rule.stated_at is not None:
            _require_quoted(own_text, rule.referral_statement or "", entry, subject="referral statement")
            stating_text = _slot_text(contents, semantic_anchor_key(rule.stated_at), entry)
        _require_quoted(stating_text, rule.natural_person_statement, entry, subject="natural-person statement")
        _require_quoted(stating_text, rule.entity_statement, entry, subject="entity statement")
        _require_stated_order(rule, entry)


def _slot_text(contents: Mapping[AnchorKey, str], key: AnchorKey, entry: SemanticMapEntry) -> str:
    text = contents.get(key)
    if text is None:
        raise RegistryValidationError(
            f"semantic map export field {entry.export_field_id!r} names a party-name rule slot "
            "the design does not have",
        )
    return text


def _require_quoted(text: str, statement: str, entry: SemanticMapEntry, *, subject: str) -> None:
    if _collapsed(statement) not in text:
        raise RegistryValidationError(
            f"semantic map export field {entry.export_field_id!r} quotes a party-name {subject} its design slot "
            f"does not contain: {statement!r}",
        )


def _require_stated_order(rule: SemanticMapPartyName, entry: SemanticMapEntry) -> None:
    statement = _collapsed(rule.natural_person_statement).casefold()
    cursor = 0
    for component in rule.composition.natural_person:
        found = statement.find(_COMPONENT_WORDS[component], cursor)
        if found < 0:
            raise RegistryValidationError(
                f"semantic map export field {entry.export_field_id!r} composes {component.value!r} where its quoted "
                "design sentence does not name it in that order",
            )
        cursor = found + len(_COMPONENT_WORDS[component])
    separator_words = _SEPARATOR_WORDS.get(rule.composition.separator)
    if separator_words is None or separator_words not in statement:
        raise RegistryValidationError(
            f"semantic map export field {entry.export_field_id!r} separates parts with "
            f"{rule.composition.separator!r}, which its quoted design sentence does not state",
        )
    entity = _collapsed(rule.entity_statement).casefold()
    if any(_COMPONENT_WORDS[component] not in entity for component in rule.composition.entity):
        raise RegistryValidationError(
            f"semantic map export field {entry.export_field_id!r} composes an entity from parts its quoted "
            "design sentence does not ask for",
        )


def _collapsed(text: str) -> str:
    return _WHITESPACE.sub(" ", text).strip()


__all__ = ["verify_party_name_statements"]
