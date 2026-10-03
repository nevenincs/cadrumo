"""Typed projection of the governed IVA-deduction applicability catalogue."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date
from typing import Final

from ....core.iva_deduction_fact import IvaDeductionEvidenceAuthority, IvaDeductionFactKind
from .errors import RegistryValidationError
from .facts.resolution import required_mapping_entry
from .facts.string_mapping import (
    MappingValueWhitespace,
    StringMappingFact,
    StringMappingPolicy,
)
from .governed_fact_scope import GovernedFactSource
from .schema_base import DateAxis

_ENTRY_SUBJECT: Final = "IVA deduction catalogue"

_FACT_ID = "iva-deduction-applicability-catalogue"
_KIND_ORDER_KEY = "kind.order"
_AUTHORITY_ORDER_KEY = "evidence_authority.order"
_KIND_OWNER_ONLY_KEY = "kind.owner_only"
_KIND_INVESTMENT_KEY = "kind.investment_acquisition"


@dataclass(frozen=True, slots=True)
class IvaDeductionCatalogue:
    """The dated, typed projection of fact 0085."""

    declarations: Mapping[str, str]
    kinds: tuple[IvaDeductionFactKind, ...]
    authorities: tuple[IvaDeductionEvidenceAuthority, ...]

    def require_kind(self, value: object) -> IvaDeductionFactKind:
        """Return a kind only when fact 0085 declares it."""
        if isinstance(value, IvaDeductionFactKind):
            token = value
        elif isinstance(value, str):
            raw = value.strip()
            if not raw:
                raise RegistryValidationError("IVA deduction kind must be a non-empty string token")
            try:
                token = IvaDeductionFactKind(raw, _registry_validated=True)
            except (TypeError, ValueError) as exc:
                raise RegistryValidationError("IVA deduction kind must be a non-empty string token") from exc
        else:
            raise RegistryValidationError("IVA deduction kind must be a string token")
        if token not in self.kinds:
            raise RegistryValidationError(
                f"IVA deduction kind {str(token)!r} is not declared by fact {_FACT_ID!r}",
            )
        return token

    def require_authority(self, value: object) -> IvaDeductionEvidenceAuthority:
        """Return an evidence authority only when fact 0085 declares it."""
        if isinstance(value, IvaDeductionEvidenceAuthority):
            token = value
        elif isinstance(value, str):
            raw = value.strip()
            if not raw:
                raise RegistryValidationError("IVA deduction evidence authority must be a non-empty string token")
            try:
                token = IvaDeductionEvidenceAuthority(raw, _registry_validated=True)
            except (TypeError, ValueError) as exc:
                raise RegistryValidationError(
                    "IVA deduction evidence authority must be a non-empty string token",
                ) from exc
        else:
            raise RegistryValidationError("IVA deduction evidence authority must be a string token")
        if token not in self.authorities:
            raise RegistryValidationError(
                f"IVA deduction evidence authority {str(token)!r} is not declared by fact {_FACT_ID!r}",
            )
        return token

    def projection(self, key: str) -> frozenset[IvaDeductionFactKind]:
        """Return a fact-0085 kind projection, preserving no Python catalogue."""
        raw = required_mapping_entry(self.declarations, key, subject=_ENTRY_SUBJECT)
        values = frozenset(self.require_kind(value) for value in _csv(raw))
        return values

    def required_authority(self, kind: IvaDeductionFactKind) -> IvaDeductionEvidenceAuthority:
        """Return the registry-declared evidence family for ``kind``."""
        token = self.require_kind(kind)
        return self.require_authority(self.declarations.get(f"kind.required_authority.{token}"))

    def authority_for_role(self, role: str) -> IvaDeductionEvidenceAuthority:
        """Return a named authority projection declared by fact 0085."""
        return self.require_authority(self.declarations.get(f"evidence_authority.{role}"))

    @property
    def ordinary_kinds(self) -> tuple[IvaDeductionFactKind, ...]:
        """Return authored kind order excluding the owner-only projection."""
        owner_only = self.projection(_KIND_OWNER_ONLY_KEY)
        return tuple(kind for kind in self.kinds if kind not in owner_only)


def _csv(raw: str) -> tuple[str, ...]:
    values = tuple(token.strip() for token in raw.split(",") if token.strip())
    if not values or len(values) != len(set(values)):
        raise RegistryValidationError("IVA deduction catalogue entries must be unique non-empty tokens")
    return values


_ENTRIES_POLICY = StringMappingPolicy(subject=_ENTRY_SUBJECT, value_whitespace=MappingValueWhitespace.PRESERVE)


_ENTRIES_FACT = StringMappingFact(fact_id=_FACT_ID, date_axis=DateAxis.FILING_PERIOD, policy=_ENTRIES_POLICY)


def resolve_iva_deduction_catalogue(
    *,
    effective_date: date | None = None,
    authority: GovernedFactSource | None = None,
) -> IvaDeductionCatalogue:
    """Resolve all fifteen IVA-deduction axis tokens from fact 0085."""
    declarations = _ENTRIES_FACT.resolve_scoped_entries(effective_date=effective_date, authority=authority)
    kinds = tuple(
        IvaDeductionFactKind(value, _registry_validated=True)
        for value in _csv(required_mapping_entry(declarations, _KIND_ORDER_KEY, subject=_ENTRY_SUBJECT))
    )
    authorities = tuple(
        IvaDeductionEvidenceAuthority(value, _registry_validated=True)
        for value in _csv(required_mapping_entry(declarations, _AUTHORITY_ORDER_KEY, subject=_ENTRY_SUBJECT))
    )
    catalogue = IvaDeductionCatalogue(
        declarations=declarations,
        kinds=kinds,
        authorities=authorities,
    )
    if len(set(kinds)) != len(kinds) or len(set(authorities)) != len(authorities):
        raise RegistryValidationError("IVA deduction catalogue contains duplicate ordered tokens")
    # Validate every declared projection and required authority eagerly. A
    # malformed fact must fail at the registry boundary, not in arithmetic.
    catalogue.projection(_KIND_OWNER_ONLY_KEY)
    catalogue.projection(_KIND_INVESTMENT_KEY)
    for kind in kinds:
        catalogue.required_authority(kind)
    catalogue.authority_for_role("invoice")
    return catalogue


def require_iva_deduction_fact_kind(
    value: object,
    *,
    effective_date: date | None = None,
    authority: GovernedFactSource | None = None,
) -> IvaDeductionFactKind:
    """Project one IVA deduction kind through fact 0085."""
    return resolve_iva_deduction_catalogue(
        effective_date=effective_date,
        authority=authority,
    ).require_kind(value)


def require_iva_deduction_evidence_authority(
    value: object,
    *,
    effective_date: date | None = None,
    authority: GovernedFactSource | None = None,
) -> IvaDeductionEvidenceAuthority:
    """Project one evidence authority through fact 0085."""
    return resolve_iva_deduction_catalogue(
        effective_date=effective_date,
        authority=authority,
    ).require_authority(value)


def iva_deduction_fact_kinds(
    *,
    effective_date: date | None = None,
    authority: GovernedFactSource | None = None,
) -> tuple[IvaDeductionFactKind, ...]:
    """Return all non-owner-only deduction kinds in registry order."""
    return resolve_iva_deduction_catalogue(
        effective_date=effective_date,
        authority=authority,
    ).ordinary_kinds


def is_iva_deduction_kind(
    value: object,
    projection_key: str,
    *,
    effective_date: date | None = None,
    authority: GovernedFactSource | None = None,
) -> bool:
    """Test membership in one fact-0085 projection without local values."""
    catalogue = resolve_iva_deduction_catalogue(effective_date=effective_date, authority=authority)
    token = catalogue.require_kind(value)
    return token in catalogue.projection(projection_key)


def invoice_evidence_authority(
    *,
    effective_date: date | None = None,
    authority: GovernedFactSource | None = None,
) -> IvaDeductionEvidenceAuthority:
    """Return the registry-declared authority for invoice-linked evidence."""
    return resolve_iva_deduction_catalogue(
        effective_date=effective_date,
        authority=authority,
    ).authority_for_role("invoice")


__all__ = [
    "IvaDeductionCatalogue",
    "invoice_evidence_authority",
    "is_iva_deduction_kind",
    "iva_deduction_fact_kinds",
    "require_iva_deduction_evidence_authority",
    "require_iva_deduction_fact_kind",
    "resolve_iva_deduction_catalogue",
]
