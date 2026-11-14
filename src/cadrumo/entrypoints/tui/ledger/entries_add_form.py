"""The facts the Add entry form asks for, read from the request schema the runtime served.

The runtime describes ``ledger.add`` and the description carries the request's
JSON schema. Which facts exist, which are required, which choices a closed one
offers, the catalogue key of each fact's words and of each choice's words,
which facts are picked from a served entry-option family and which the form's
door fills from its session are all read from that schema, never composed
here. A served fact without a form annotation is not put to a person. JSON
Schema cannot express a rule across facts (a source jurisdiction a profile's
regime requires, a personal entry with business figures); the operation
refuses those with its own words, which the form shows as they were recorded.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Literal

from ....application.operations.form_field_annotation import OperationFormFieldV1, served_form_field
from ....core.type_guards import is_object_list, is_str_keyed_dict
from .link_picker import LedgerLinkFieldV1


class LedgerAddFormUnavailableError(ValueError):
    """The served schema cannot be offered as a form: a required fact has no place on it."""


@dataclass(frozen=True, slots=True)
class LedgerAddFieldV1:
    """One text or closed-choice fact of the request, as the schema served it, with its served word keys."""

    name: str
    required: bool
    label_key: str
    choices: tuple[str, ...]
    default: str | None
    choice_label_keys: Mapping[str, str] = field(default_factory=lambda: MappingProxyType({}))

    @property
    def is_choice(self) -> bool:
        """Whether the schema closes this fact to a list of tokens."""
        return bool(self.choices)


@dataclass(frozen=True, slots=True)
class LedgerAddFormV1:
    """Every fact the form offers, in the order the schema lists them.

    ``fields`` are typed or chosen on the form, ``links`` are picked from served
    entry-option families, and ``profile_fields`` are filled by the door with
    the exact profile its session was admitted for.
    """

    fields: tuple[LedgerAddFieldV1, ...]
    links: tuple[LedgerLinkFieldV1, ...] = ()
    profile_fields: tuple[str, ...] = ()

    @property
    def required(self) -> tuple[LedgerAddFieldV1, ...]:
        """The facts the operation will not take without."""
        return tuple(field for field in self.fields if field.required)

    @property
    def optional(self) -> tuple[LedgerAddFieldV1, ...]:
        """The facts the operation takes but does not need."""
        return tuple(field for field in self.fields if not field.required)

    def field(self, name: str) -> LedgerAddFieldV1:
        """Return one offered fact by name."""
        for candidate in self.fields:
            if candidate.name == name:
                return candidate
        raise KeyError(name)


def _non_null_branches(prop: Mapping[str, object]) -> list[object]:
    """The schemas a fact may take once an optional fact's null branch is set aside."""
    branches = prop.get("anyOf")
    if branches is None:
        return [prop]
    if not is_object_list(branches):
        return []
    return [branch for branch in branches if not (is_str_keyed_dict(branch) and branch.get("type") == "null")]


def _text_schema(prop: Mapping[str, object]) -> dict[str, object] | None:
    """The string schema of a fact: the fact itself, or the one non-null branch of an optional one."""
    present = _non_null_branches(prop)
    if len(present) != 1:
        return None
    branch = present[0]
    if not is_str_keyed_dict(branch) or branch.get("type") != "string" or "format" in branch:
        return None
    return branch


def _choices(text: Mapping[str, object]) -> tuple[str, ...]:
    tokens = text.get("enum")
    if tokens is None:
        return ()
    if not is_object_list(tokens) or not all(isinstance(token, str) for token in tokens):
        raise LedgerAddFormUnavailableError("a closed fact lists something other than tokens")
    return tuple(str(token) for token in tokens)


def _default(prop: Mapping[str, object]) -> str | None:
    value = prop.get("default")
    return value if isinstance(value, str) else None


def _served_facts(schema: Mapping[str, object]) -> tuple[dict[str, object], frozenset[str]]:
    properties = schema.get("properties")
    required = schema.get("required")
    if not is_str_keyed_dict(properties) or not is_object_list(required):
        raise LedgerAddFormUnavailableError("the served schema lists no facts")
    return properties, frozenset(str(name) for name in required)


def _annotation(name: str, prop: Mapping[str, object]) -> OperationFormFieldV1 | None:
    try:
        return served_form_field(prop)
    except ValueError as error:
        raise LedgerAddFormUnavailableError(f"fact {name!r}: {error}") from None


def _asked_field(
    name: str, prop: Mapping[str, object], annotation: OperationFormFieldV1, label_key: str, *, required: bool
) -> LedgerAddFieldV1:
    """One fact the form types or chooses; a fact served to a person that is not text has no place on it."""
    text = _text_schema(prop)
    if text is None:
        raise LedgerAddFormUnavailableError(f"fact {name!r} is served to a person but is not text")
    return LedgerAddFieldV1(
        name=name,
        required=required,
        label_key=label_key,
        choices=_choices(text),
        default=_default(prop),
        choice_label_keys=MappingProxyType(dict(annotation.choice_label_keys)),
    )


type _Placement = LedgerAddFieldV1 | LedgerLinkFieldV1 | Literal["profile"] | None


def _place(name: str, prop: object, *, required: bool) -> _Placement:
    """Where one served fact goes: asked, picked, bound to the profile, or ``None`` when it has no place."""
    if not is_str_keyed_dict(prop):
        raise LedgerAddFormUnavailableError(f"fact {name!r} is served without a schema")
    annotation = _annotation(name, prop)
    if annotation is None:
        return None
    if annotation.bound == "profile":
        return "profile"
    label_key = annotation.label_key
    if label_key is None:
        return None
    if annotation.entry_option_family is None:
        return _asked_field(name, prop, annotation, label_key, required=required)
    # A pick may be left unchosen, so a required fact cannot be served as one.
    if required:
        return None
    return LedgerLinkFieldV1(field=name, family=annotation.entry_option_family, label_key=label_key)


def read_served_form(schema: Mapping[str, object]) -> LedgerAddFormV1:
    """Read the form of ``schema`` from the form annotations it serves.

    A required fact the schema neither puts to a person nor binds to the
    session cannot be asked for, so the form is refused rather than opened
    without it; so is a fact put to a person that is not a text or closed choice.
    """
    properties, required = _served_facts(schema)
    fields: list[LedgerAddFieldV1] = []
    links: list[LedgerLinkFieldV1] = []
    profile_fields: list[str] = []
    unplaceable: list[str] = []
    for name, prop in properties.items():
        placed = _place(name, prop, required=name in required)
        if placed is None:
            if name in required:
                unplaceable.append(name)
        elif placed == "profile":
            profile_fields.append(name)
        elif isinstance(placed, LedgerLinkFieldV1):
            links.append(placed)
        else:
            fields.append(placed)
    if unplaceable:
        raise LedgerAddFormUnavailableError(f"required facts without a place on the form: {sorted(unplaceable)}")
    if not any(field.required for field in fields):
        raise LedgerAddFormUnavailableError("the served schema asks a person for no required fact")
    return LedgerAddFormV1(tuple(fields), links=tuple(links), profile_fields=tuple(profile_fields))


__all__ = [
    "LedgerAddFieldV1",
    "LedgerAddFormUnavailableError",
    "LedgerAddFormV1",
    "read_served_form",
]
