"""An edit refused after its values were admitted settles under the refusal that stopped it.

The edit's own refusal, "state the value again", is right only for a value the
edit refused. When the values were admitted and a later stage refused -- the
recalculation, or the authority it reads -- the operator needs that stage's
code, words and door. This module keeps exactly those, value-free, across the
edit contract and turns them back into the registered error the edit settles
under. The words keep only the public registry coordinates their sentence
names -- a modelo, an ejercicio, a period, a casilla, a binding -- and a
sentence that needs anything else is not served. A sentence may also name
words derived from those coordinates alone, such as a binding's declared
label: the coordinates travel and the words are worded again where the edit
settles, so no free text crosses the edit contract.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Final

from ...core.errors.error_codes import ErrorCode, get_registered_error_code, public_error_context
from ...core.errors.hierarchy import CadrumoError, RecordedRegisteredError
from ...core.external_constants import OutputLanguage
from ...core.i18n.render import extract_placeholders, lookup_translation
from ...core.operator_action_enums import (
    ActionArgumentStatus,
    ActionConditionality,
    ActionEvidenceProvenance,
)
from ...domain.calculations.registry.modelo_localization import binding_label_text
from ..cli_exception_preconditions import nested_terminal_precondition_verdict
from ..operations.error_detail import UNWORDED_REGISTERED_ERROR_LOCALE_KEY, served_words_language
from ..operator_actions.models import ActionArgumentBinding, ActionReference, ConditionEvidence, PreconditionVerdict
from .edit_downstream_models import (
    MODELO_EDIT_MESSAGE_KEY_PATTERN,
    ModeloEditDownstreamContextEntryV1,
    ModeloEditDownstreamRefusalV1,
    modelo_edit_downstream_context_is_public,
)

#: The one evidence a value-free door states: the edit's values were admitted before the stage refused.
_DOOR_EVIDENCE_ID: Final[str] = "modelo.work.edit.downstream_refusal"

type _DerivedWords = Callable[[Mapping[str, str], OutputLanguage], str]


@dataclass(frozen=True, slots=True)
class _Derivation:
    """How one name a sentence may use is worded again from public coordinates alone.

    ``coordinates`` are the public coordinates the words read. ``read_from``
    names, for a coordinate the refusal does not hold under its own key, the
    key of the refusal's context that holds it; the value found there travels
    only under the coordinate's key and only if the coordinate's grammar
    admits it.
    """

    coordinates: tuple[str, ...]
    words: _DerivedWords
    read_from: Mapping[str, str] = field(default_factory=lambda: MappingProxyType({}))


def _binding_label(coordinates: Mapping[str, str], language: OutputLanguage) -> str:
    return binding_label_text(coordinates["modelo"], coordinates["binding_id"], locale=language.value)


#: Words a sentence may name that are worded from public coordinates alone, by name. Only the coordinates are
#: kept; the words are worded again in the language served. The calculation's input-required sentences hold the
#: binding under ``binding`` and the box it feeds under ``boxes``: the binding travels as its id and is worded as its
#: declared label, and the box travels as its casilla coordinate.
_DERIVED_WORDS: Final[Mapping[str, _Derivation]] = MappingProxyType(
    {
        "binding_label": _Derivation(coordinates=("binding_id", "modelo"), words=_binding_label),
        "binding": _Derivation(
            coordinates=("binding_id", "modelo"),
            words=_binding_label,
            read_from=MappingProxyType({"binding_id": "binding"}),
        ),
        "boxes": _Derivation(
            coordinates=("casilla_ids",),
            words=lambda coordinates, _language: coordinates["casilla_ids"],
            read_from=MappingProxyType({"casilla_ids": "boxes"}),
        ),
    }
)


def _placeholders_in_every_language(key: str) -> frozenset[str] | None:
    """The values ``key``'s sentences need in every served language, or ``None`` when it is not a worded key."""
    if re.fullmatch(MODELO_EDIT_MESSAGE_KEY_PATTERN, key) is None:
        return None
    names: set[str] = set()
    for language in OutputLanguage:
        template = lookup_translation(key, locale=language.value)
        if template is None:
            return None
        names.update(extract_placeholders(template))
    return frozenset(names)


def _public_context(error: CadrumoError, derived: frozenset[str]) -> dict[str, str]:
    """The error's context entries that are public registry coordinates, as the error envelope renders them.

    A coordinate the ``derived`` words read from another key of the context is
    taken from there when its grammar admits the value found.
    """
    rendered = public_error_context(error) or {}
    public = {key: value for key, value in rendered.items() if modelo_edit_downstream_context_is_public(key, value)}
    for name in sorted(derived):
        for coordinate, source in _DERIVED_WORDS[name].read_from.items():
            value = rendered.get(source)
            if (
                coordinate not in public
                and value is not None
                and modelo_edit_downstream_context_is_public(coordinate, value)
            ):
                public[coordinate] = value
    return public


def _worded(
    error: CadrumoError, registered: ErrorCode
) -> tuple[str | None, tuple[ModeloEditDownstreamContextEntryV1, ...]]:
    """The key the refusal is worded by and the public coordinates it names, if nothing else completes it.

    The error's own key names its cause, unless its code's registry entry
    owns the public message; only an error without one takes its code's
    catalogue key. A cause's key that needs a value other than a public
    coordinate is not swapped for the code's broader sentence, which can state
    another cause: none is chosen, and the sentence then names the code. Only
    the coordinates the sentence names, or derives its words from, travel.
    """
    own = error.translated_message
    registry_owned = registered.public_message_from_registry or ".canonical_" in registered.message_key
    key = registered.message_key if registry_owned or own is None else own
    names = _placeholders_in_every_language(key)
    if names is None:
        return None, ()
    derived = frozenset(names & _DERIVED_WORDS.keys())
    carried = (names - derived) | {coordinate for name in derived for coordinate in _DERIVED_WORDS[name].coordinates}
    public = _public_context(error, derived) if carried else {}
    if not carried <= public.keys():
        return None, ()
    return key, tuple(ModeloEditDownstreamContextEntryV1(key=name, value=public[name]) for name in sorted(carried))


def downstream_refusal(error: CadrumoError) -> ModeloEditDownstreamRefusalV1:
    """Keep the registered refusal a stage after value admission raised as its code, words and value-free door.

    An argument the refusal's verdict resolved from its own facts is kept by
    name only, as still to be given, because its value stays behind.
    """
    registered = get_registered_error_code(error)
    message_key, context = _worded(error, registered)
    verdict = nested_terminal_precondition_verdict(error)
    if verdict is None:
        return ModeloEditDownstreamRefusalV1(error_code=registered.code, message_key=message_key, context=context)
    return ModeloEditDownstreamRefusalV1(
        error_code=registered.code,
        message_key=message_key,
        context=context,
        failed_condition_id=verdict.failed_condition_id,
        recovery_action=None if verdict.action is None else ActionReference(action_id=verdict.action.action_id),
        argument_names=tuple(binding.argument_name for binding in verdict.argument_bindings),
        no_recovery_outcome=verdict.no_recovery_outcome,
    )


def _door(refusal: ModeloEditDownstreamRefusalV1) -> PreconditionVerdict | None:
    """The refusal's door as a verdict whose one fact is that the edit's values were admitted."""
    condition = refusal.failed_condition_id
    if condition is None:
        return None
    evidence = (
        ConditionEvidence(
            condition_id=condition,
            evidence_id=_DOOR_EVIDENCE_ID,
            provenance=ActionEvidenceProvenance.APPLICATION_STATE,
            values={"edit_values_admitted": True},
        ),
    )
    if refusal.recovery_action is None:
        return PreconditionVerdict(
            failed_condition_id=condition,
            evidence=evidence,
            no_recovery_outcome=refusal.no_recovery_outcome,
            conditionality=ActionConditionality.NOT_APPLICABLE,
        )
    names = refusal.argument_names
    return PreconditionVerdict(
        failed_condition_id=condition,
        evidence=evidence,
        action=refusal.recovery_action,
        argument_bindings=tuple(
            ActionArgumentBinding(argument_name=name, status=ActionArgumentStatus.MISSING) for name in names
        ),
        missing_argument_names=names,
        conditionality=ActionConditionality.REQUIRES_ARGUMENTS if names else ActionConditionality.IMMEDIATE,
    )


def downstream_refusal_error(refusal: ModeloEditDownstreamRefusalV1) -> RecordedRegisteredError:
    """The registered error an edit settles under when a stage after value admission refused it.

    Its key is completed by the public coordinates it carries and the words
    derived from them, worded in the language served; without a key, the
    sentence names the refusal's code.
    """
    if refusal.message_key is None:
        return RecordedRegisteredError(
            refusal.error_code,
            translated_message=UNWORDED_REGISTERED_ERROR_LOCALE_KEY,
            context={"error_code": refusal.error_code},
            precondition_verdict=_door(refusal),
        )
    coordinates = {entry.key: entry.value for entry in refusal.context}
    names = _placeholders_in_every_language(refusal.message_key) or frozenset()
    language = served_words_language()
    derived = {
        name: derivation.words(coordinates, language)
        for name, derivation in _DERIVED_WORDS.items()
        if name in names and all(source in coordinates for source in derivation.coordinates)
    }
    return RecordedRegisteredError(
        refusal.error_code,
        translated_message=refusal.message_key,
        context={**coordinates, **derived} or None,
        precondition_verdict=_door(refusal),
    )


__all__ = ["downstream_refusal", "downstream_refusal_error"]
