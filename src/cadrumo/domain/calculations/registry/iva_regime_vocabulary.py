"""Typed authority projection for IVA regime semantics."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from ...deadlines.models import IVARegime
from .errors import RegistryValidationError
from .facts.resolution import (
    UNIQUE_REFERENCES_REQUIREMENT,
    optional_unique_mapping_tokens,
    required_mapping_entry,
    unique_mapping_tokens,
)
from .governed_fact_scope import GovernedFactSource
from .iva_schema_vocabulary_source import (
    SCHEMA_VOCABULARY_SUBJECT,
    UNIQUE_TOKENS_REQUIREMENT,
    resolve_scoped_schema_entries,
)
from .iva_schema_vocabulary_tokens import _require_token

_REGIME_ORDER_KEY = "iva_regime.order"

_REGIME_DEFAULT_KEY = "iva_regime.default_token"

_REGIME_NO_APLICA_KEY = "iva_regime.no_aplica_token"

_REGIME_SELF_ASSESSMENT_KEY = "iva_regime.self_assessment_order"

_REGIME_SIMPLIFICADO_KEY = "iva_regime.simplificado_token"

_REGIME_REAGP_KEY = "iva_regime.reagp_token"

_REGIME_EXENTO_KEY = "iva_regime.exento_token"

_REGIME_PREFIX = "iva_regime."


@dataclass(frozen=True, slots=True)
class IvaRegimeDefinition:
    """One registry-declared IVA regime and its deadline semantics."""

    token: IVARegime
    description: str
    deadline_applicability: str
    legal_refs: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class IvaRegimeCatalogue:
    """Typed projection of the dated IVA regime vocabulary."""

    definitions: tuple[IvaRegimeDefinition, ...]
    default_token: IVARegime
    no_aplica_token: IVARegime
    self_assessment_tokens: frozenset[IVARegime]

    @property
    def all_regimes(self) -> frozenset[IVARegime]:
        """Return every IVA regime declared by the registry."""
        return frozenset(definition.token for definition in self.definitions)

    @property
    def selectable_regimes(self) -> tuple[IVARegime, ...]:
        """Return IVA regimes that may be selected by an operator."""
        return tuple(definition.token for definition in self.definitions if definition.token != self.no_aplica_token)

    def require(self, value: object) -> IVARegime:
        """Validate and return one registry-declared IVA regime."""
        return _require_token(value, IVARegime, self.all_regimes, "IVA regime")

    def definition(self, value: object) -> IvaRegimeDefinition:
        """Return the registry definition for one IVA regime."""
        token = self.require(value)
        return next(definition for definition in self.definitions if definition.token == token)


def resolve_iva_regime_catalogue(
    *,
    effective_date: date | None = None,
    authority: GovernedFactSource | None = None,
) -> IvaRegimeCatalogue:
    """Resolve the dated IVA-regime vocabulary from governed facts."""
    entries = resolve_scoped_schema_entries(effective_date=effective_date, authority=authority)
    definitions: list[IvaRegimeDefinition] = []
    for raw_token in unique_mapping_tokens(
        entries, _REGIME_ORDER_KEY, subject=SCHEMA_VOCABULARY_SUBJECT, requirement=UNIQUE_TOKENS_REQUIREMENT
    ):
        token = IVARegime(raw_token)
        prefix = f"{_REGIME_PREFIX}{raw_token}"
        if required_mapping_entry(entries, f"{prefix}.value", subject=SCHEMA_VOCABULARY_SUBJECT) != raw_token:
            raise RegistryValidationError(f"IVA regime token {raw_token!r} declares a mismatched value")
        definitions.append(
            IvaRegimeDefinition(
                token=token,
                description=required_mapping_entry(entries, f"{prefix}.description", subject=SCHEMA_VOCABULARY_SUBJECT),
                deadline_applicability=required_mapping_entry(
                    entries, f"{prefix}.deadline_applicability", subject=SCHEMA_VOCABULARY_SUBJECT
                ),
                legal_refs=optional_unique_mapping_tokens(
                    entries,
                    f"{prefix}.legal_refs",
                    subject=SCHEMA_VOCABULARY_SUBJECT,
                    requirement=UNIQUE_REFERENCES_REQUIREMENT,
                ),
            ),
        )
    catalogue = IvaRegimeCatalogue(
        definitions=tuple(definitions),
        default_token=IVARegime(
            required_mapping_entry(entries, _REGIME_DEFAULT_KEY, subject=SCHEMA_VOCABULARY_SUBJECT)
        ),
        no_aplica_token=IVARegime(
            required_mapping_entry(entries, _REGIME_NO_APLICA_KEY, subject=SCHEMA_VOCABULARY_SUBJECT)
        ),
        self_assessment_tokens=frozenset(
            IVARegime(raw_token)
            for raw_token in unique_mapping_tokens(
                entries,
                _REGIME_SELF_ASSESSMENT_KEY,
                subject=SCHEMA_VOCABULARY_SUBJECT,
                requirement=UNIQUE_TOKENS_REQUIREMENT,
            )
        ),
    )
    if catalogue.default_token not in catalogue.all_regimes:
        raise RegistryValidationError("IVA default regime is not declared in the regime order")
    if catalogue.no_aplica_token not in catalogue.all_regimes:
        raise RegistryValidationError("IVA NO_APLICA regime is not declared in the regime order")
    if not catalogue.self_assessment_tokens.issubset(catalogue.all_regimes):
        raise RegistryValidationError("IVA self-assessment regimes must be declared in the regime order")
    for semantic_key in (_REGIME_SIMPLIFICADO_KEY, _REGIME_REAGP_KEY, _REGIME_EXENTO_KEY):
        semantic_token = IVARegime(required_mapping_entry(entries, semantic_key, subject=SCHEMA_VOCABULARY_SUBJECT))
        if semantic_token not in catalogue.all_regimes:
            raise RegistryValidationError(f"IVA regime semantic token {semantic_key!r} is not declared")
    return catalogue


def default_iva_regime(
    *,
    effective_date: date | None = None,
    authority: GovernedFactSource | None = None,
) -> IVARegime:
    """Return the registry-declared default IVA regime."""
    return resolve_iva_regime_catalogue(
        effective_date=effective_date,
        authority=authority,
    ).default_token


def require_iva_regime(
    value: object,
    *,
    effective_date: date | None = None,
    authority: GovernedFactSource | None = None,
) -> IVARegime:
    """Validate one value against the dated IVA-regime vocabulary."""
    return resolve_iva_regime_catalogue(
        effective_date=effective_date,
        authority=authority,
    ).require(value)


def iva_regime_choices(
    *,
    effective_date: date | None = None,
    authority: GovernedFactSource | None = None,
) -> tuple[IVARegime, ...]:
    """Return selectable IVA regimes in registry order."""
    return resolve_iva_regime_catalogue(
        effective_date=effective_date,
        authority=authority,
    ).selectable_regimes


def iva_regime_no_aplica_token(
    *,
    effective_date: date | None = None,
    authority: GovernedFactSource | None = None,
) -> IVARegime:
    """Return the registry-declared ``NO_APLICA`` IVA regime token."""
    return resolve_iva_regime_catalogue(
        effective_date=effective_date,
        authority=authority,
    ).no_aplica_token


def iva_regime_self_assessment_tokens(
    *,
    effective_date: date | None = None,
    authority: GovernedFactSource | None = None,
) -> frozenset[IVARegime]:
    """Return IVA regimes marked for self-assessment by the registry."""
    return resolve_iva_regime_catalogue(
        effective_date=effective_date,
        authority=authority,
    ).self_assessment_tokens


def _iva_regime_semantic_token(
    key: str,
    *,
    effective_date: date | None = None,
    authority: GovernedFactSource | None = None,
) -> IVARegime:
    entries = resolve_scoped_schema_entries(effective_date=effective_date, authority=authority)
    return require_iva_regime(
        required_mapping_entry(entries, key, subject=SCHEMA_VOCABULARY_SUBJECT),
        effective_date=effective_date,
        authority=authority,
    )


def iva_regime_simplificado_token(
    *,
    effective_date: date | None = None,
    authority: GovernedFactSource | None = None,
) -> IVARegime:
    """Return the registry-declared simplified IVA regime token."""
    return _iva_regime_semantic_token(
        _REGIME_SIMPLIFICADO_KEY,
        effective_date=effective_date,
        authority=authority,
    )


def iva_regime_reagp_token(
    *,
    effective_date: date | None = None,
    authority: GovernedFactSource | None = None,
) -> IVARegime:
    """Return the registry-declared REAGP IVA regime token."""
    return _iva_regime_semantic_token(
        _REGIME_REAGP_KEY,
        effective_date=effective_date,
        authority=authority,
    )


def iva_regime_exento_token(
    *,
    effective_date: date | None = None,
    authority: GovernedFactSource | None = None,
) -> IVARegime:
    """Return the registry-declared exempt IVA regime token."""
    return _iva_regime_semantic_token(
        _REGIME_EXENTO_KEY,
        effective_date=effective_date,
        authority=authority,
    )


__all__ = [
    "IvaRegimeCatalogue",
    "IvaRegimeDefinition",
    "default_iva_regime",
    "iva_regime_choices",
    "iva_regime_exento_token",
    "iva_regime_no_aplica_token",
    "iva_regime_reagp_token",
    "iva_regime_self_assessment_tokens",
    "iva_regime_simplificado_token",
    "require_iva_regime",
    "resolve_iva_regime_catalogue",
]
