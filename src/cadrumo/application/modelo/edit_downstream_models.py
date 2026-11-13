"""Downstream refusal record of a Modelo edit.

A stage after value admission, such as the recalculation, can refuse under its
own registered code. This module holds the value-free record of that refusal
and the allowlist of public registry coordinates its sentence may name.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from types import MappingProxyType
from typing import Annotated, Final

from pydantic import Field, model_validator

from ...core.errors.hierarchy import pydantic_validation_boundary
from ...core.identifier_grammar import FIELD_KEY_PATTERN, NamespacedId
from ...core.operator_action_enums import NoRecoveryOutcome
from ..operator_actions.models import ActionReference
from .edit_contract import EditModel

MODELO_EDIT_MESSAGE_KEY_PATTERN: Final[str] = r"^[a-z][a-z0-9_]*(?:\.[a-z0-9_]+)+$"
"""The shape of a catalogue key an edit refusal may name; a sentence of free text never matches it."""

_YEAR_VALUE: Final[str] = r"^[0-9]{4}$"
_MODELO_VALUE: Final[str] = r"^[0-9]{3}$"
_PERIOD_VALUE: Final[str] = r"^(?:0[1-9]|1[0-2]|0A|[1-4][TP]|EXT-[1-4]T|EVENT-[0-9]{1,3})$"
_CASILLA_GRAMMAR: Final[str] = r"[A-Za-z0-9][A-Za-z0-9._:-]{0,63}"
_REGISTRY_ID_GRAMMAR: Final[str] = r"[a-z0-9][a-z0-9_.-]{0,127}"
_MAX_LISTED_IDENTIFIERS = 32
_MAX_ARGUMENT_NAMES = 64
_MAX_DOWNSTREAM_CONTEXT_ENTRIES = 16


def _one(token: str) -> str:
    return rf"^{token}$"


def _listed(token: str) -> str:
    """A list of ``token`` as the error envelope renders a collection: comma and space between members."""
    return rf"^{token}(?:, {token}){{0,{_MAX_LISTED_IDENTIFIERS - 1}}}$"


MODELO_EDIT_DOWNSTREAM_PUBLIC_CONTEXT: Final[Mapping[str, str]] = MappingProxyType(
    {
        "binding_id": _one(_REGISTRY_ID_GRAMMAR),
        "binding_ids": _listed(_REGISTRY_ID_GRAMMAR),
        "blocking_filing_year": _YEAR_VALUE,
        "blocking_period": _PERIOD_VALUE,
        "casilla_id": _one(_CASILLA_GRAMMAR),
        "casilla_ids": _listed(_CASILLA_GRAMMAR),
        "export_layout_id": _one(_REGISTRY_ID_GRAMMAR),
        "filing_year": _YEAR_VALUE,
        "modelo": _MODELO_VALUE,
        "parameter_id": _one(_REGISTRY_ID_GRAMMAR),
        "period": _PERIOD_VALUE,
        "source_filing_year": _YEAR_VALUE,
        "source_modelo": _MODELO_VALUE,
        "source_period": _PERIOD_VALUE,
        "target_period": _PERIOD_VALUE,
        "target_year": _YEAR_VALUE,
        "tax_year": _YEAR_VALUE,
        "unfiled_period": _PERIOD_VALUE,
    }
)
"""The context a downstream refusal may carry: each key, and the grammar its value must match.

Every key names a public registry coordinate -- a modelo, an ejercicio, a
period code, a casilla, a binding, a parameter or an export layout -- never a
filer's value. The grammar is what keeps it so: a key whose producer put an
amount, a name, a tax ID, a path or a sentence under it fails its grammar and
is dropped, never carried.
"""


def modelo_edit_downstream_context_is_public(key: str, value: str) -> bool:
    """Whether ``key`` is a public coordinate a downstream refusal may carry and ``value`` is shaped as one."""
    pattern = MODELO_EDIT_DOWNSTREAM_PUBLIC_CONTEXT.get(key)
    return pattern is not None and re.fullmatch(pattern, value) is not None


class ModeloEditDownstreamContextEntryV1(EditModel):
    """One public registry coordinate a downstream refusal's sentence names."""

    key: Annotated[str, Field(min_length=1, max_length=64, pattern=r"^[a-z][a-z0-9_]*$")]
    value: Annotated[str, Field(min_length=1, max_length=4096)]

    @model_validator(mode="after")
    @pydantic_validation_boundary
    def _public_coordinate(self) -> ModeloEditDownstreamContextEntryV1:
        """Only a key of the public context, with a value its grammar admits."""
        if not modelo_edit_downstream_context_is_public(self.key, self.value):
            raise ValueError("a downstream refusal carries only a public registry coordinate")
        return self


def _is_empty(value: object) -> bool:
    """Whether a tuple member holds nothing, so the serialized record leaves it out."""
    return value == ()


class ModeloEditDownstreamRefusalV1(EditModel):
    """The registered refusal a stage after value admission raised, kept as itself and nothing more.

    It holds the refusal's registered code, a catalogue key whose sentence
    needs no filer's value to be finished (none when the refusal has no such
    key, and the code's unworded sentence then names the code), the public
    registry coordinates that sentence names (see
    :data:`MODELO_EDIT_DOWNSTREAM_PUBLIC_CONTEXT`), and its door with every
    value taken out: the failed condition, then either the action that clears
    it and the names of that action's arguments, or the closed outcome when no
    action does. No other context, evidence value or argument value travels,
    so neither a filer's value nor a name or tax ID can reach operation
    persistence or a rendered message.
    """

    error_code: Annotated[str, Field(min_length=3, max_length=128, pattern=r"^[A-Z][A-Z0-9]*(?:_[A-Z0-9]+)+$")]
    message_key: Annotated[str, Field(min_length=3, max_length=256, pattern=MODELO_EDIT_MESSAGE_KEY_PATTERN)] | None = (
        None
    )
    context: Annotated[
        tuple[ModeloEditDownstreamContextEntryV1, ...], Field(max_length=_MAX_DOWNSTREAM_CONTEXT_ENTRIES)
    ] = Field(default=(), exclude_if=_is_empty)
    failed_condition_id: NamespacedId | None = None
    recovery_action: ActionReference | None = None
    argument_names: Annotated[
        tuple[Annotated[str, Field(min_length=1, max_length=128, pattern=FIELD_KEY_PATTERN)], ...],
        Field(max_length=_MAX_ARGUMENT_NAMES),
    ] = ()
    no_recovery_outcome: NoRecoveryOutcome | None = None

    @model_validator(mode="after")
    @pydantic_validation_boundary
    def _context_completes_its_sentence(self) -> ModeloEditDownstreamRefusalV1:
        """Context completes the sentence of a key, so it travels only with one, each key once and in order."""
        keys = tuple(entry.key for entry in self.context)
        if keys and self.message_key is None:
            raise ValueError("a downstream refusal carries context only for the sentence it completes")
        if keys != tuple(sorted(set(keys))):
            raise ValueError("a downstream refusal names each context key once, in order")
        return self

    @model_validator(mode="after")
    @pydantic_validation_boundary
    def _one_door_shape(self) -> ModeloEditDownstreamRefusalV1:
        """A door names its condition and exactly one way out; no door names neither."""
        if self.failed_condition_id is None:
            if self.recovery_action is not None or self.no_recovery_outcome is not None or self.argument_names:
                raise ValueError("a downstream refusal door names the condition that failed")
            return self
        if (self.recovery_action is None) == (self.no_recovery_outcome is None):
            raise ValueError("a downstream refusal door is either an action or a closed outcome")
        if self.recovery_action is None and self.argument_names:
            raise ValueError("a closed outcome takes no action arguments")
        if len(set(self.argument_names)) != len(self.argument_names):
            raise ValueError("a downstream refusal door names each argument once")
        return self
