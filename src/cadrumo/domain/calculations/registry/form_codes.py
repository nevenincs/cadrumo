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

from collections.abc import Mapping
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


def resolve_form_codes_leased(fact_id: str, *, authority: GovernedFactSource | None = None) -> FormCodes:
    """Resolve one form-code fact from the authority, the pinned scope, else a published lease.

    For a reader that may stand outside every operation, such as a transport model
    validated on the client side. The lease lasts only for the read, and every entry
    comes from one generation.
    """
    selected = authority or governed_facts_in_scope()
    if selected is not None:
        return resolve_form_codes(fact_id, authority=selected)

    from .authority import bundled_indexed_authority

    with bundled_indexed_authority().operation() as operation:
        return resolve_form_codes(fact_id, authority=operation)


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


__all__ = ["FormCodes", "RegistryCodedEnum", "resolve_form_codes", "resolve_form_codes_leased"]
