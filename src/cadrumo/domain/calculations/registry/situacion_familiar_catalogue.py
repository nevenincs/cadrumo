"""Typed projection of the Art. 82 LIRPF family-situation vocabulary."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Final

from ...contribuyente.renta_codes import SituacionFamiliar
from .errors import RegistryValidationError
from .facts.declared_token import require_declared_registry_token
from .facts.resolution import required_mapping_entry, unique_mapping_tokens
from .facts.string_mapping import (
    BooleanTokenCase,
    MappingValueWhitespace,
    StringMappingFact,
    StringMappingPolicy,
    required_mapping_boolean,
    unique_mapping_legal_refs,
)
from .governed_fact_scope import GovernedFactSource
from .schema_base import DateAxis

_ENTRY_SUBJECT: Final = "family-situation vocabulary"

_FACT_ID = "lirpf-family-situation-vocabulary"
_ORDER_KEY = "situacion_familiar.order"
_PREFIX = "situacion_familiar."
_VALUE_SUFFIX = ".value"
_DESCRIPTION_SUFFIX = ".description"
_LEGAL_REFS_SUFFIX = ".legal_refs"
_MONOPARENTAL_SUFFIX = ".monoparental_required"


@dataclass(frozen=True, slots=True)
class SituacionFamiliarDefinition:
    """One registry-declared Art. 82 family-situation token."""

    token: SituacionFamiliar
    description: str
    legal_refs: tuple[str, ...]
    monoparental_required: bool


@dataclass(frozen=True, slots=True)
class SituacionFamiliarCatalogue:
    """Complete typed projection of the dated family-situation fact."""

    definitions: tuple[SituacionFamiliarDefinition, ...]

    @property
    def choices(self) -> tuple[SituacionFamiliar, ...]:
        """Return the registry-declared choices in authored order."""
        return tuple(definition.token for definition in self.definitions)

    @property
    def all_situaciones(self) -> frozenset[SituacionFamiliar]:
        """Return the registry-declared family-situation tokens."""
        return frozenset(definition.token for definition in self.definitions)

    def require(self, value: object) -> SituacionFamiliar:
        """Project one token only when the selected authority declares it."""
        return require_declared_registry_token(
            value,
            token_type=SituacionFamiliar,
            declared=self.all_situaciones,
            subject="family-situation",
            fact_id=_FACT_ID,
        )

    def definition(self, value: object) -> SituacionFamiliarDefinition:
        """Return the complete legal definition for one declared token."""
        token = self.require(value)
        return next(item for item in self.definitions if item.token == token)


_ENTRIES_POLICY = StringMappingPolicy(subject=_ENTRY_SUBJECT, value_whitespace=MappingValueWhitespace.PRESERVE)


_ENTRIES_FACT = StringMappingFact(fact_id=_FACT_ID, date_axis=DateAxis.FILING_PERIOD, policy=_ENTRIES_POLICY)


def resolve_situacion_familiar_catalogue(
    *,
    effective_date: date | None = None,
    authority: GovernedFactSource | None = None,
) -> SituacionFamiliarCatalogue:
    """Resolve the dated Art. 82 vocabulary through the facts authority."""
    entries = _ENTRIES_FACT.resolve_scoped_entries(effective_date=effective_date, authority=authority)
    definitions: list[SituacionFamiliarDefinition] = []
    for raw_token in unique_mapping_tokens(entries, _ORDER_KEY, subject=_ENTRY_SUBJECT):
        try:
            token = SituacionFamiliar.from_registry(raw_token)
        except (TypeError, ValueError) as exc:
            raise RegistryValidationError("family-situation vocabulary contains an invalid token") from exc
        prefix = f"{_PREFIX}{raw_token}"
        if required_mapping_entry(entries, f"{prefix}{_VALUE_SUFFIX}", subject=_ENTRY_SUBJECT) != raw_token:
            raise RegistryValidationError(f"family-situation token {raw_token!r} declares a mismatched value")
        definitions.append(
            SituacionFamiliarDefinition(
                token=token,
                description=required_mapping_entry(entries, f"{prefix}{_DESCRIPTION_SUFFIX}", subject=_ENTRY_SUBJECT),
                legal_refs=unique_mapping_legal_refs(entries, f"{prefix}{_LEGAL_REFS_SUFFIX}", subject=_ENTRY_SUBJECT),
                monoparental_required=required_mapping_boolean(
                    entries,
                    f"{prefix}{_MONOPARENTAL_SUFFIX}",
                    subject=_ENTRY_SUBJECT,
                    case=BooleanTokenCase.CASE_INSENSITIVE,
                ),
            ),
        )
    catalogue = SituacionFamiliarCatalogue(definitions=tuple(definitions))
    if len(catalogue.all_situaciones) != len(catalogue.definitions):
        raise RegistryValidationError("family-situation vocabulary contains duplicate tokens")
    return catalogue


def require_situacion_familiar(
    value: object,
    *,
    effective_date: date | None = None,
    authority: GovernedFactSource | None = None,
) -> SituacionFamiliar:
    """Return a family-situation token only when the fact declares it."""
    return resolve_situacion_familiar_catalogue(
        effective_date=effective_date,
        authority=authority,
    ).require(value)


def situacion_familiar_choices(
    *,
    effective_date: date | None = None,
    authority: GovernedFactSource | None = None,
) -> tuple[SituacionFamiliar, ...]:
    """Return family-situation choices in authority order."""
    return resolve_situacion_familiar_catalogue(
        effective_date=effective_date,
        authority=authority,
    ).choices


def situacion_familiar_monoparental_required(
    value: object,
    *,
    effective_date: date | None = None,
    authority: GovernedFactSource | None = None,
) -> bool:
    """Return the registry-declared Art. 82.1.2ª mapping for one token."""
    return (
        resolve_situacion_familiar_catalogue(
            effective_date=effective_date,
            authority=authority,
        )
        .definition(value)
        .monoparental_required
    )


__all__ = [
    "SituacionFamiliarCatalogue",
    "SituacionFamiliarDefinition",
    "require_situacion_familiar",
    "resolve_situacion_familiar_catalogue",
    "situacion_familiar_choices",
    "situacion_familiar_monoparental_required",
]
