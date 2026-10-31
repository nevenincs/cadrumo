"""Form codes the registry declares, read by the typed code that means them.

A closed vocabulary keeps its members in code, because the program branches on
what each member means. The code a member carries on a form or in a stored record
is a form datum, so the registry declares it in a governed mapping fact. The member
name stays semantic, and nothing in code repeats the letter or number.

:class:`RegistryCodedEnum` projects one such vocabulary. A member's value is its
semantic token. :attr:`RegistryCodedEnum.code` reads its form code. A model field
validates from either the code or the semantic token and serializes as the code,
so stored records and public payloads keep the bytes they already carry.

Reading a code needs a generation-pinned governed-fact scope, as every catalogue
does. Outside one the read refuses rather than guess.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import date
from enum import StrEnum
from types import MappingProxyType
from typing import Self, override

from pydantic import GetCoreSchemaHandler
from pydantic_core import CoreSchema, core_schema

from ....core.errors.hierarchy import CoreValidationError, pydantic_validation_boundary
from .errors import RegistryValidationError
from .facts.resolution import unique_mapping_tokens
from .facts.string_mapping import MappingValueWhitespace, StringMappingFact, StringMappingPolicy
from .governed_fact_scope import GovernedFactSource, governed_facts_in_scope
from .schema_base import DateAxis

_ROLE_ROUTING_FACT = "modelo-role-routing"
_FORM_ROW_CODES_FACT = "form-row-codes"


@dataclass(frozen=True, slots=True)
class FormCodes:
    """The resolved entries of one form-code fact."""

    fact_id: str
    entries: Mapping[str, str]

    def code(self, key: str) -> str:
        """Return the code declared under ``key``, refusing an undeclared one."""
        try:
            return self.entries[key]
        except KeyError as exc:
            raise RegistryValidationError(f"form-code fact {self.fact_id!r} declares no {key!r}") from exc

    def codes(self, key: str) -> frozenset[str]:
        """Return the comma-separated codes declared under ``key``."""
        return frozenset(self.ordered_codes(key))

    def ordered_codes(self, key: str) -> tuple[str, ...]:
        """Return the comma-separated codes declared under ``key``, in authored order."""
        return unique_mapping_tokens(self.entries, key, subject=f"form-code fact {self.fact_id!r}")

    def integer(self, key: str) -> int:
        """Return the whole number declared under ``key``."""
        raw = self.code(key)
        try:
            return int(raw)
        except ValueError as exc:
            raise RegistryValidationError(f"form-code fact {self.fact_id!r} {key!r} is not a number: {raw!r}") from exc

    def under(self, prefix: str) -> Mapping[str, str]:
        """Return the entries below ``prefix.``, keyed by the remainder of the key."""
        lead = f"{prefix}."
        return MappingProxyType(
            {key.removeprefix(lead): value for key, value in self.entries.items() if key.startswith(lead)},
        )


def resolve_form_codes(
    fact_id: str,
    *,
    effective_date: date | None = None,
    authority: GovernedFactSource | None = None,
) -> FormCodes:
    """Resolve one form-code fact from the explicit authority or the pinned scope."""
    fact = StringMappingFact(
        fact_id=fact_id,
        date_axis=DateAxis.FILING_PERIOD,
        policy=StringMappingPolicy(
            subject=f"form-code fact {fact_id!r}",
            value_whitespace=MappingValueWhitespace.STRIP,
        ),
    )
    return FormCodes(
        fact_id=fact_id,
        entries=fact.resolve_scoped_entries(effective_date=effective_date, authority=authority),
    )


def form_codes_in_scope(fact_id: str = _FORM_ROW_CODES_FACT) -> FormCodes | None:
    """Return one form-code fact for a model validator, or ``None`` outside every authority scope.

    A model is validated twice: in the runtime, which holds the pinned authority and
    enforces the form's geometry, and in a client reading the runtime's result, which
    holds none and has nothing to decide. The client keeps the model's technical bound.
    Only a validator may use this reader. Code that needs the value itself resolves it
    with :func:`resolve_form_codes`, which refuses outside a scope.
    """
    return None if governed_facts_in_scope() is None else resolve_form_codes(fact_id)


def exceeds_form_bound(count: int, key: str) -> bool:
    """Return whether ``count`` is past the ``form-row-codes`` bound in the current scope."""
    codes = form_codes_in_scope()
    return codes is not None and count > codes.integer(key)


def require_form_width(value: str | None, key: str) -> str | None:
    """Return ``value`` unless the scope's ``form-row-codes`` fact declares another width for ``key``."""
    codes = form_codes_in_scope()
    if value is not None and codes is not None and str(len(value)) not in codes.codes(key):
        raise CoreValidationError(f"a value does not have the width the form declares for {key}")
    return value


def require_form_fit(value: str | None, key: str) -> str | None:
    """Return ``value`` unless it is longer than the scope's ``form-row-codes`` fact declares for ``key``."""
    if value is not None and exceeds_form_bound(len(value), key):
        raise CoreValidationError(f"a value is longer than the form declares for {key}")
    return value


def form_width_validator(key: str) -> Callable[[str], str]:
    """Return a Pydantic validator that applies :func:`require_form_width` to a required string."""

    @pydantic_validation_boundary
    def validate(value: str) -> str:
        require_form_width(value, key)
        return value

    return validate


def form_fit_validator(key: str) -> Callable[[str], str]:
    """Return a Pydantic validator that applies :func:`require_form_fit` to a required string."""

    @pydantic_validation_boundary
    def validate(value: str) -> str:
        require_form_fit(value, key)
        return value

    return validate


def form_for_role(role: str, *, authority: GovernedFactSource | None = None) -> str:
    """Return the form that holds ``role``, from the registry's role routing."""
    return resolve_form_codes(_ROLE_ROUTING_FACT, authority=authority).code(role)


def forms_for_role(role: str, *, authority: GovernedFactSource | None = None) -> frozenset[str]:
    """Return the forms a rule named ``role`` covers, from the registry's role routing."""
    return resolve_form_codes(_ROLE_ROUTING_FACT, authority=authority).codes(role)


def form_for_role_in_scope(role: str) -> str | None:
    """Return the form that holds ``role`` for a model validator, or ``None`` outside every scope.

    Only a validator may use this reader; see :func:`form_codes_in_scope`.
    """
    codes = form_codes_in_scope(_ROLE_ROUTING_FACT)
    return None if codes is None else codes.code(role)


def differs_from_role(value: object, role: str) -> bool:
    """Return whether the scope's registry names another form than ``value`` for ``role``."""
    form = form_for_role_in_scope(role)
    return form is not None and str(value) != form


def form_role_validator(role: str) -> Callable[[str], str]:
    """Return a Pydantic validator that refuses any form but the one holding ``role`` in the scope."""

    @pydantic_validation_boundary
    def validate(value: str) -> str:
        if differs_from_role(value, role):
            raise CoreValidationError(f"this record belongs to the form holding {role}")
        return value

    return validate


class RegistryCodedEnum(StrEnum):
    """A closed vocabulary whose form codes the registry declares.

    A subclass names its fact and key prefix in ``_form_code_source``, and the
    fact declares one ``<prefix>.<member value>`` entry per member. A fact that
    omits a member, adds one, or repeats a code is refused, so the two sides
    cannot drift apart.
    """

    @classmethod
    def _form_code_source(cls) -> tuple[str, str]:
        """Return the fact id and key prefix that declare this vocabulary."""
        raise NotImplementedError

    @classmethod
    def form_codes(
        cls,
        *,
        effective_date: date | None = None,
        authority: GovernedFactSource | None = None,
    ) -> Mapping[Self, str]:
        """Return every member's declared code."""
        fact_id, prefix = cls._form_code_source()
        declared = resolve_form_codes(fact_id, effective_date=effective_date, authority=authority).under(prefix)
        members = {member.value for member in cls}
        if set(declared) != members:
            raise RegistryValidationError(
                f"form-code fact {fact_id!r} {prefix!r} declares {sorted(declared)}, "
                f"which is not the vocabulary {sorted(members)}",
            )
        if len(set(declared.values())) != len(declared):
            raise RegistryValidationError(f"form-code fact {fact_id!r} {prefix!r} repeats a code")
        return MappingProxyType({member: declared[member.value] for member in cls})

    @property
    def code(self) -> str:
        """Return this member's code from the pinned scope."""
        return type(self).form_codes()[self]

    @classmethod
    def from_code(
        cls,
        code: str,
        *,
        effective_date: date | None = None,
        authority: GovernedFactSource | None = None,
    ) -> Self:
        """Return the member declared with ``code``, refusing any other text."""
        for member, declared in cls.form_codes(effective_date=effective_date, authority=authority).items():
            if declared == code:
                return member
        raise ValueError(f"{code!r} is not a {cls.__name__} code")

    @classmethod
    @override
    def _missing_(cls, value: object) -> Self | None:
        """Read a stored or wire code as the member it declares."""
        return cls.from_code(value) if isinstance(value, str) else None

    @classmethod
    def _validated(cls, value: object) -> Self:
        if isinstance(value, cls):
            return value
        if isinstance(value, str):
            return cls(value)
        raise CoreValidationError(f"{cls.__name__} must be a declared code")

    @classmethod
    def __get_pydantic_core_schema__(cls, _source_type: object, _handler: GetCoreSchemaHandler) -> CoreSchema:
        """Validate a member, semantic token or code, and serialize as the code."""
        return core_schema.no_info_plain_validator_function(
            pydantic_validation_boundary(cls._validated),
            json_schema_input_schema=core_schema.str_schema(),
            serialization=core_schema.plain_serializer_function_ser_schema(
                lambda member: member.code if isinstance(member, RegistryCodedEnum) else member,
                return_schema=core_schema.str_schema(),
            ),
        )


__all__ = [
    "FormCodes",
    "RegistryCodedEnum",
    "differs_from_role",
    "exceeds_form_bound",
    "form_codes_in_scope",
    "form_for_role_in_scope",
    "form_role_validator",
    "require_form_fit",
    "require_form_width",
    "resolve_form_codes",
]
