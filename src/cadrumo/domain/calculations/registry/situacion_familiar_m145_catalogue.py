"""Typed projection of the Modelo 145 family-situation vocabulary."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Final

from ...contribuyente.renta_codes import SituacionFamiliarM145
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

_ENTRY_SUBJECT: Final = "Modelo 145 family-situation vocabulary"

_FACT_ID = "lirpf-modelo-145-family-situation-vocabulary"
_ORDER_KEY = "situacion_familiar_m145.order"
_PREFIX = "situacion_familiar_m145."
_VALUE_SUFFIX = ".value"
_DESCRIPTION_SUFFIX = ".description"
_LEGAL_REFS_SUFFIX = ".legal_refs"
_ELIGIBLE_SUFFIX = ".supplementary_reduction_eligible"


@dataclass(frozen=True, slots=True)
class SituacionFamiliarM145Definition:
    """One registry-declared Modelo 145 family-situation token."""

    token: SituacionFamiliarM145
    description: str
    legal_refs: tuple[str, ...]
    supplementary_reduction_eligible: bool


@dataclass(frozen=True, slots=True)
class SituacionFamiliarM145Catalogue:
    """Complete typed projection of the dated Modelo 145 fact."""

    definitions: tuple[SituacionFamiliarM145Definition, ...]

    @property
    def choices(self) -> tuple[SituacionFamiliarM145, ...]:
        """Return the registry-declared choices in authored order."""
        return tuple(definition.token for definition in self.definitions)

    @property
    def all_situaciones(self) -> frozenset[SituacionFamiliarM145]:
        """Return the registry-declared family-situation tokens."""
        return frozenset(definition.token for definition in self.definitions)

    def require(self, value: object) -> SituacionFamiliarM145:
        """Project one token only when the selected authority declares it."""
        return require_declared_registry_token(
            value,
            token_type=SituacionFamiliarM145,
            declared=self.all_situaciones,
            subject="Modelo 145 family-situation",
            fact_id=_FACT_ID,
        )

    def definition(self, value: object) -> SituacionFamiliarM145Definition:
        """Return the complete legal definition for one declared token."""
        token = self.require(value)
        return next(item for item in self.definitions if item.token == token)


_ENTRIES_POLICY = StringMappingPolicy(subject=_ENTRY_SUBJECT, value_whitespace=MappingValueWhitespace.PRESERVE)


_ENTRIES_FACT = StringMappingFact(fact_id=_FACT_ID, date_axis=DateAxis.FILING_PERIOD, policy=_ENTRIES_POLICY)


def resolve_situacion_familiar_m145_catalogue(
    *,
    effective_date: date | None = None,
    authority: GovernedFactSource | None = None,
) -> SituacionFamiliarM145Catalogue:
    """Resolve the dated Modelo 145 vocabulary through the facts authority."""
    entries = _ENTRIES_FACT.resolve_scoped_entries(effective_date=effective_date, authority=authority)
    definitions: list[SituacionFamiliarM145Definition] = []
    for raw_token in unique_mapping_tokens(entries, _ORDER_KEY, subject=_ENTRY_SUBJECT):
        try:
            token = SituacionFamiliarM145.from_registry(raw_token)
        except (TypeError, ValueError) as exc:
            raise RegistryValidationError(
                "Modelo 145 family-situation vocabulary contains an invalid token",
            ) from exc
        prefix = f"{_PREFIX}{raw_token}"
        if required_mapping_entry(entries, f"{prefix}{_VALUE_SUFFIX}", subject=_ENTRY_SUBJECT) != raw_token:
            raise RegistryValidationError(
                f"Modelo 145 family-situation token {raw_token!r} declares a mismatched value"
            )
        definitions.append(
            SituacionFamiliarM145Definition(
                token=token,
                description=required_mapping_entry(entries, f"{prefix}{_DESCRIPTION_SUFFIX}", subject=_ENTRY_SUBJECT),
                legal_refs=unique_mapping_legal_refs(entries, f"{prefix}{_LEGAL_REFS_SUFFIX}", subject=_ENTRY_SUBJECT),
                supplementary_reduction_eligible=required_mapping_boolean(
                    entries,
                    f"{prefix}{_ELIGIBLE_SUFFIX}",
                    subject=_ENTRY_SUBJECT,
                    case=BooleanTokenCase.CASE_INSENSITIVE,
                ),
            ),
        )
    catalogue = SituacionFamiliarM145Catalogue(definitions=tuple(definitions))
    if len(catalogue.all_situaciones) != len(catalogue.definitions):
        raise RegistryValidationError("Modelo 145 family-situation vocabulary contains duplicate tokens")
    return catalogue


def require_situacion_familiar_m145(
    value: object,
    *,
    effective_date: date | None = None,
    authority: GovernedFactSource | None = None,
) -> SituacionFamiliarM145:
    """Return a Modelo 145 token only when fact 0142 declares it."""
    return resolve_situacion_familiar_m145_catalogue(
        effective_date=effective_date,
        authority=authority,
    ).require(value)


__all__ = [
    "SituacionFamiliarM145Catalogue",
    "SituacionFamiliarM145Definition",
    "require_situacion_familiar_m145",
    "resolve_situacion_familiar_m145_catalogue",
]
