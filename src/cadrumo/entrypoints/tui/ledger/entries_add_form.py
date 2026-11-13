"""The facts the Add entry form asks for, read from the request schema the runtime served.

The runtime describes ``ledger.add`` and the description carries the request's
JSON schema. Which facts exist, which are required and which choices a closed
one offers are read from that schema, never composed here. JSON Schema cannot
express a rule across facts (a source jurisdiction a profile's regime requires,
a personal entry with business figures); the operation refuses those with its
own words, which the form shows as they were recorded.
"""

from __future__ import annotations

from collections.abc import Collection, Mapping
from dataclasses import dataclass

from ....core.type_guards import is_object_list, is_str_keyed_dict


class LedgerAddFormUnavailableError(ValueError):
    """The served schema cannot be offered as a form: a required fact has no place on it."""


@dataclass(frozen=True, slots=True)
class LedgerAddFieldV1:
    """One text or closed-choice fact of the request, as the schema served it."""

    name: str
    required: bool
    choices: tuple[str, ...]
    default: str | None

    @property
    def is_choice(self) -> bool:
        """Whether the schema closes this fact to a list of tokens."""
        return bool(self.choices)


@dataclass(frozen=True, slots=True)
class LedgerAddFormV1:
    """Every fact the form offers, in the order the schema lists them."""

    fields: tuple[LedgerAddFieldV1, ...]

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


def _read_field(name: str, prop: object, *, required: bool) -> LedgerAddFieldV1 | None:
    """One offered fact, or ``None`` for an optional fact that is not text."""
    text = _text_schema(prop) if is_str_keyed_dict(prop) else None
    if text is None or not is_str_keyed_dict(prop):
        if required:
            raise LedgerAddFormUnavailableError(f"required fact {name!r} is not text")
        return None
    return LedgerAddFieldV1(name=name, required=required, choices=_choices(text), default=_default(prop))


def read_served_form(
    schema: Mapping[str, object], *, offered: Collection[str], supplied: Collection[str]
) -> LedgerAddFormV1:
    """Read the form of ``schema``, offering the facts the screen has words for.

    ``supplied`` names the facts the screen's door fills itself (the exact
    profile). A required fact that is neither offered nor supplied, or that is
    not a text or closed choice, cannot be asked for, so the form is refused
    rather than opened without it.
    """
    properties, required = _served_facts(schema)
    unplaceable = sorted(name for name in required if name not in offered and name not in supplied)
    if unplaceable:
        raise LedgerAddFormUnavailableError(f"required facts without a place on the form: {unplaceable}")
    read = (_read_field(name, prop, required=name in required) for name, prop in properties.items() if name in offered)
    return LedgerAddFormV1(tuple(field for field in read if field is not None))


__all__ = ["LedgerAddFieldV1", "LedgerAddFormUnavailableError", "LedgerAddFormV1", "read_served_form"]
