"""Typed authority projections for Modelo 303 territory and regime composition."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation

from ...deadlines.models import M303RegimeComposition, M303TaxTerritory
from ...iva.regimen_simplificado_rows import M303RegimenSimplificadoScope
from .errors import RegistryValidationError
from .facts.resolution import UNIQUE_REFERENCES_REQUIREMENT, required_mapping_entry, unique_mapping_tokens
from .governed_fact_scope import GovernedFactSource
from .iva_schema_vocabulary_source import (
    SCHEMA_VOCABULARY_SUBJECT,
    UNIQUE_TOKENS_REQUIREMENT,
    resolve_scoped_schema_entries,
)

_TERRITORY_ORDER_KEY = "tax_territory.order"

_COMPOSITION_ORDER_KEY = "m303_regime_composition.order"

_TERRITORY_PREFIX = "tax_territory."

_COMPOSITION_PREFIX = "m303_regime_composition."


@dataclass(frozen=True, slots=True)
class M303TaxTerritoryDefinition:
    """One registry-declared Modelo 303 tax-territory token and semantics."""

    token: M303TaxTerritory
    description: str
    legal_refs: tuple[str, ...]
    is_foral: bool
    state_attribution_ratio: Decimal
    exclusively_foral_mark: str


@dataclass(frozen=True, slots=True)
class M303TaxTerritoryCatalogue:
    """Typed projection of the dated Modelo 303 territory vocabulary."""

    definitions: tuple[M303TaxTerritoryDefinition, ...]

    @property
    def all_territories(self) -> frozenset[M303TaxTerritory]:
        """Return every Modelo 303 tax territory declared by the registry."""
        return frozenset(definition.token for definition in self.definitions)

    @property
    def choices(self) -> tuple[M303TaxTerritory, ...]:
        """Return Modelo 303 tax-territory choices in registry order."""
        return tuple(definition.token for definition in self.definitions)

    @property
    def foral_token(self) -> M303TaxTerritory:
        """Return the sole foral territory declared by the registry."""
        matches = tuple(definition.token for definition in self.definitions if definition.is_foral)
        if len(matches) != 1:
            raise RegistryValidationError("Modelo 303 tax-territory catalogue must declare exactly one foral token")
        return matches[0]

    def require(self, value: object) -> M303TaxTerritory:
        """Validate and return one registry-declared Modelo 303 territory."""
        if isinstance(value, M303TaxTerritory):
            token = value
        elif isinstance(value, str):
            raw = value.strip()
            if not raw:
                raise RegistryValidationError("Modelo 303 tax-territory token must be non-empty")
            if raw not in {str(member) for member in self.all_territories}:
                raise RegistryValidationError(
                    f"Modelo 303 tax-territory token {raw!r} is not declared by the facts registry",
                )
            token = M303TaxTerritory.from_registry(raw)
        else:
            raise RegistryValidationError("Modelo 303 tax-territory token must be a string token")
        if token not in self.all_territories:
            raise RegistryValidationError(
                f"Modelo 303 tax-territory token {str(token)!r} is not declared by the facts registry",
            )
        return token

    def definition(self, value: object) -> M303TaxTerritoryDefinition:
        """Return the registry definition for one Modelo 303 territory."""
        token = self.require(value)
        return next(definition for definition in self.definitions if definition.token == token)


@dataclass(frozen=True, slots=True)
class M303RegimeCompositionDefinition:
    """One registry-declared Modelo 303 regime-composition token and semantics."""

    token: M303RegimeComposition
    description: str
    export_code: str
    simplified_scope: str
    legal_refs: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class M303RegimeCompositionCatalogue:
    """Typed projection of the dated Modelo 303 composition vocabulary."""

    definitions: tuple[M303RegimeCompositionDefinition, ...]

    @property
    def all_compositions(self) -> frozenset[M303RegimeComposition]:
        """Return every Modelo 303 regime composition declared by the registry."""
        return frozenset(definition.token for definition in self.definitions)

    @property
    def choices(self) -> tuple[M303RegimeComposition, ...]:
        """Return Modelo 303 regime-composition choices in registry order."""
        return tuple(definition.token for definition in self.definitions)

    def require(self, value: object) -> M303RegimeComposition:
        """Validate and return one registry-declared Modelo 303 composition."""
        if isinstance(value, M303RegimeComposition):
            token = value
        elif isinstance(value, str):
            raw = value.strip()
            if not raw:
                raise RegistryValidationError("Modelo 303 regime-composition token must be non-empty")
            if raw not in {str(member) for member in self.all_compositions}:
                raise RegistryValidationError(
                    f"Modelo 303 regime-composition token {raw!r} is not declared by the facts registry",
                )
            token = M303RegimeComposition.from_registry(raw)
        else:
            raise RegistryValidationError("Modelo 303 regime-composition token must be a string token")
        if token not in self.all_compositions:
            raise RegistryValidationError(
                f"Modelo 303 regime-composition token {str(token)!r} is not declared by the facts registry",
            )
        return token

    def definition(self, value: object) -> M303RegimeCompositionDefinition:
        """Return the registry definition for one Modelo 303 composition."""
        token = self.require(value)
        return next(definition for definition in self.definitions if definition.token == token)

    def require_simplified_scope(self, value: object) -> M303RegimenSimplificadoScope:
        """Validate and return one simplified-regime scope some composition declares."""
        if not isinstance(value, str):
            raise RegistryValidationError("M303 simplified-regime scope must be a string token")
        if value not in {definition.simplified_scope for definition in self.definitions}:
            raise RegistryValidationError(
                f"M303 simplified-regime scope {str(value)!r} is not declared by the facts registry",
            )
        if isinstance(value, M303RegimenSimplificadoScope):
            return value
        return M303RegimenSimplificadoScope.from_registry(value)


def resolve_m303_tax_territory_catalogue(
    *,
    effective_date: date | None = None,
    authority: GovernedFactSource | None = None,
) -> M303TaxTerritoryCatalogue:
    """Resolve the dated Modelo 303 territory vocabulary and semantics."""
    entries = resolve_scoped_schema_entries(effective_date=effective_date, authority=authority)
    definitions: list[M303TaxTerritoryDefinition] = []
    for raw_token in unique_mapping_tokens(
        entries, _TERRITORY_ORDER_KEY, subject=SCHEMA_VOCABULARY_SUBJECT, requirement=UNIQUE_TOKENS_REQUIREMENT
    ):
        try:
            token = M303TaxTerritory.from_registry(raw_token)
            declared_value = required_mapping_entry(
                entries, f"{_TERRITORY_PREFIX}{raw_token}.value", subject=SCHEMA_VOCABULARY_SUBJECT
            )
            description = required_mapping_entry(
                entries, f"{_TERRITORY_PREFIX}{raw_token}.description", subject=SCHEMA_VOCABULARY_SUBJECT
            )
            raw_is_foral = required_mapping_entry(
                entries, f"{_TERRITORY_PREFIX}{raw_token}.is_foral", subject=SCHEMA_VOCABULARY_SUBJECT
            )
            raw_ratio = required_mapping_entry(
                entries, f"{_TERRITORY_PREFIX}{raw_token}.state_attribution_ratio", subject=SCHEMA_VOCABULARY_SUBJECT
            )
            exclusively_foral_mark = required_mapping_entry(
                entries, f"{_TERRITORY_PREFIX}{raw_token}.exclusively_foral_mark", subject=SCHEMA_VOCABULARY_SUBJECT
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise RegistryValidationError(
                f"Modelo 303 tax-territory catalogue is missing or invalid for {raw_token!r}",
            ) from exc
        if declared_value != raw_token:
            raise RegistryValidationError(f"Modelo 303 tax-territory token {raw_token!r} declares a mismatched value")
        if raw_is_foral not in {"true", "false"}:
            raise RegistryValidationError(f"Modelo 303 tax-territory token {raw_token!r} has invalid foral status")
        try:
            ratio = Decimal(raw_ratio)
        except InvalidOperation as exc:
            raise RegistryValidationError(
                f"Modelo 303 tax-territory token {raw_token!r} has an invalid state-attribution ratio",
            ) from exc
        if ratio < 0 or ratio > 100:
            raise RegistryValidationError(
                f"Modelo 303 tax-territory token {raw_token!r} has an out-of-range state-attribution ratio",
            )
        definitions.append(
            M303TaxTerritoryDefinition(
                token=token,
                description=description,
                legal_refs=unique_mapping_tokens(
                    entries,
                    f"{_TERRITORY_PREFIX}{raw_token}.legal_refs",
                    subject=SCHEMA_VOCABULARY_SUBJECT,
                    requirement=UNIQUE_REFERENCES_REQUIREMENT,
                ),
                is_foral=raw_is_foral == "true",
                state_attribution_ratio=ratio,
                exclusively_foral_mark=exclusively_foral_mark,
            ),
        )
    catalogue = M303TaxTerritoryCatalogue(definitions=tuple(definitions))
    if len(catalogue.all_territories) != len(definitions):
        raise RegistryValidationError("Modelo 303 tax-territory catalogue has duplicate tokens")
    _ = catalogue.foral_token
    return catalogue


def resolve_m303_regime_composition_catalogue(
    *,
    effective_date: date | None = None,
    authority: GovernedFactSource | None = None,
) -> M303RegimeCompositionCatalogue:
    """Resolve the dated Modelo 303 regime-composition vocabulary."""
    entries = resolve_scoped_schema_entries(effective_date=effective_date, authority=authority)
    definitions: list[M303RegimeCompositionDefinition] = []
    for raw_token in unique_mapping_tokens(
        entries, _COMPOSITION_ORDER_KEY, subject=SCHEMA_VOCABULARY_SUBJECT, requirement=UNIQUE_TOKENS_REQUIREMENT
    ):
        try:
            token = M303RegimeComposition.from_registry(raw_token)
            declared_value = required_mapping_entry(
                entries, f"{_COMPOSITION_PREFIX}{raw_token}.value", subject=SCHEMA_VOCABULARY_SUBJECT
            )
            description = required_mapping_entry(
                entries, f"{_COMPOSITION_PREFIX}{raw_token}.description", subject=SCHEMA_VOCABULARY_SUBJECT
            )
            export_code = required_mapping_entry(
                entries, f"{_COMPOSITION_PREFIX}{raw_token}.export_code", subject=SCHEMA_VOCABULARY_SUBJECT
            )
            simplified_scope = required_mapping_entry(
                entries, f"{_COMPOSITION_PREFIX}{raw_token}.simplified_scope", subject=SCHEMA_VOCABULARY_SUBJECT
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise RegistryValidationError(
                f"Modelo 303 regime-composition catalogue is missing or invalid for {raw_token!r}",
            ) from exc
        if declared_value != raw_token:
            raise RegistryValidationError(
                f"Modelo 303 regime-composition token {raw_token!r} declares a mismatched value",
            )
        if simplified_scope not in {"not_claimed", "evidence_required"}:
            raise RegistryValidationError(
                f"Modelo 303 regime-composition token {raw_token!r} has invalid simplified scope",
            )
        definitions.append(
            M303RegimeCompositionDefinition(
                token=token,
                description=description,
                export_code=export_code,
                simplified_scope=simplified_scope,
                legal_refs=unique_mapping_tokens(
                    entries,
                    f"{_COMPOSITION_PREFIX}{raw_token}.legal_refs",
                    subject=SCHEMA_VOCABULARY_SUBJECT,
                    requirement=UNIQUE_REFERENCES_REQUIREMENT,
                ),
            ),
        )
    catalogue = M303RegimeCompositionCatalogue(definitions=tuple(definitions))
    if len(catalogue.all_compositions) != len(definitions):
        raise RegistryValidationError("Modelo 303 regime-composition catalogue has duplicate tokens")
    return catalogue


def require_m303_tax_territory(
    value: object,
    *,
    effective_date: date | None = None,
    authority: GovernedFactSource | None = None,
) -> M303TaxTerritory:
    """Project one Modelo 303 territory token only when the registry governs it."""
    return resolve_m303_tax_territory_catalogue(
        effective_date=effective_date,
        authority=authority,
    ).require(value)


def m303_tax_territory_choices(
    *,
    effective_date: date | None = None,
    authority: GovernedFactSource | None = None,
) -> tuple[M303TaxTerritory, ...]:
    """Return the registry-declared territory choice order."""
    return resolve_m303_tax_territory_catalogue(
        effective_date=effective_date,
        authority=authority,
    ).choices


def m303_tax_territory_is_foral(
    value: object,
    *,
    effective_date: date | None = None,
    authority: GovernedFactSource | None = None,
) -> bool:
    """Return the registry-declared foral classification for one token."""
    catalogue = resolve_m303_tax_territory_catalogue(
        effective_date=effective_date,
        authority=authority,
    )
    return catalogue.definition(value).is_foral


def m303_tax_territory_state_attribution_ratio(
    value: object,
    *,
    effective_date: date | None = None,
    authority: GovernedFactSource | None = None,
) -> Decimal:
    """Return the registry-declared State-attribution ratio for one token."""
    catalogue = resolve_m303_tax_territory_catalogue(
        effective_date=effective_date,
        authority=authority,
    )
    return catalogue.definition(value).state_attribution_ratio


def m303_tax_territory_exclusively_foral_mark(
    value: object,
    *,
    effective_date: date | None = None,
    authority: GovernedFactSource | None = None,
) -> str:
    """Return the registry-declared Modelo 303 territory output mark."""
    catalogue = resolve_m303_tax_territory_catalogue(
        effective_date=effective_date,
        authority=authority,
    )
    return catalogue.definition(value).exclusively_foral_mark


def require_m303_regime_composition(
    value: object,
    *,
    effective_date: date | None = None,
    authority: GovernedFactSource | None = None,
) -> M303RegimeComposition:
    """Project one Modelo 303 regime-composition token from the facts registry."""
    return resolve_m303_regime_composition_catalogue(
        effective_date=effective_date,
        authority=authority,
    ).require(value)


def m303_regime_composition_choices(
    *,
    effective_date: date | None = None,
    authority: GovernedFactSource | None = None,
) -> tuple[M303RegimeComposition, ...]:
    """Return the registry-declared Modelo 303 composition choice order."""
    return resolve_m303_regime_composition_catalogue(
        effective_date=effective_date,
        authority=authority,
    ).choices


def m303_regime_composition_export_code(
    value: object,
    *,
    effective_date: date | None = None,
    authority: GovernedFactSource | None = None,
) -> str:
    """Return the registry-declared Modelo 303 composition export code."""
    return (
        resolve_m303_regime_composition_catalogue(
            effective_date=effective_date,
            authority=authority,
        )
        .definition(value)
        .export_code
    )


def m303_regime_composition_simplified_scope(
    value: object,
    *,
    effective_date: date | None = None,
    authority: GovernedFactSource | None = None,
) -> M303RegimenSimplificadoScope:
    """Project the registry-declared simplified-regime scope for a composition."""
    scope = (
        resolve_m303_regime_composition_catalogue(
            effective_date=effective_date,
            authority=authority,
        )
        .definition(value)
        .simplified_scope
    )
    return M303RegimenSimplificadoScope.from_registry(scope)


def require_m303_regimen_simplificado_scope(
    value: object,
    *,
    effective_date: date | None = None,
    authority: GovernedFactSource | None = None,
) -> M303RegimenSimplificadoScope:
    """Validate one persisted simplified-regime scope against the dated composition fact."""
    return resolve_m303_regime_composition_catalogue(
        effective_date=effective_date,
        authority=authority,
    ).require_simplified_scope(value)


__all__ = [
    "M303RegimeCompositionCatalogue",
    "M303RegimeCompositionDefinition",
    "M303TaxTerritoryCatalogue",
    "M303TaxTerritoryDefinition",
    "m303_regime_composition_choices",
    "m303_regime_composition_export_code",
    "m303_regime_composition_simplified_scope",
    "m303_tax_territory_choices",
    "m303_tax_territory_exclusively_foral_mark",
    "m303_tax_territory_is_foral",
    "m303_tax_territory_state_attribution_ratio",
    "require_m303_regime_composition",
    "require_m303_regimen_simplificado_scope",
    "require_m303_tax_territory",
    "resolve_m303_regime_composition_catalogue",
    "resolve_m303_tax_territory_catalogue",
]
