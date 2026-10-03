"""Typed projections for the dated IRPF regime vocabulary fact."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date
from typing import Final

from ....core.time.clock import today_madrid
from ...deadlines.models import IrpfEstimationRegime, IrpfSpecialRegime
from .errors import RegistryValidationError
from .facts.resolution import required_mapping_entry, unique_mapping_tokens
from .facts.string_mapping import (
    MappingValueWhitespace,
    StringMappingFact,
    StringMappingPolicy,
    unique_mapping_legal_refs,
)
from .governed_fact_scope import (
    GovernedFactSource,
    cache_governed_projection,
    governed_facts_in_scope,
    require_governed_fact_authority,
    validating_governed_facts,
)
from .schema_base import DateAxis

_ENTRY_SUBJECT: Final = "IRPF regime vocabulary"

_FACT_ID = "irpf-regime-vocabulary"
_ESTIMATION_ORDER_KEY = "irpf_estimation_regime.order"
_ESTIMATION_PREFIX = "irpf_estimation_regime."
_SPECIAL_ORDER_KEY = "irpf_special_regime.order"
_SPECIAL_PREFIX = "irpf_special_regime."


@dataclass(frozen=True, slots=True)
class IrpfEstimationRegimeDefinition:
    """One registry-declared estimation-regime token and its semantics."""

    token: IrpfEstimationRegime
    description: str
    tax_regime: str
    filing_modelos: tuple[str, ...]
    legal_refs: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class IrpfSpecialRegimeDefinition:
    """One registry-declared special-regime token and its semantics."""

    token: IrpfSpecialRegime
    description: str
    tax_regime: str
    filing_modelos: tuple[str, ...]
    window_years: int | None
    legal_refs: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class IrpfRegimeVocabulary:
    """The complete typed projection of fact ``irpf-regime-vocabulary``."""

    estimation_regimes: tuple[IrpfEstimationRegimeDefinition, ...]
    special_regimes: tuple[IrpfSpecialRegimeDefinition, ...]

    @property
    def all_estimation_regimes(self) -> frozenset[IrpfEstimationRegime]:
        """Return every declared estimation regime."""
        return frozenset(item.token for item in self.estimation_regimes)

    @property
    def all_special_regimes(self) -> frozenset[IrpfSpecialRegime]:
        """Return every declared special regime."""
        return frozenset(item.token for item in self.special_regimes)

    def require_estimation_regime(self, value: object) -> IrpfEstimationRegime:
        """Return one declared estimation regime or refuse it."""
        if isinstance(value, IrpfEstimationRegime):
            token = value
        elif isinstance(value, str):
            raw = value.strip()
            if not raw:
                raise RegistryValidationError("IRPF estimation-regime token must be non-empty")
            try:
                token = IrpfEstimationRegime(raw, _registry_validated=True)
            except (TypeError, ValueError) as exc:
                raise RegistryValidationError("IRPF estimation-regime token must be a non-empty string") from exc
        else:
            raise RegistryValidationError("IRPF estimation-regime token must be a string token")
        if token not in self.all_estimation_regimes:
            raise RegistryValidationError(
                f"IRPF estimation-regime token {str(token)!r} is not declared by fact {_FACT_ID!r}",
            )
        return token

    def require_special_regime(self, value: object) -> IrpfSpecialRegime:
        """Return one declared special regime or refuse it."""
        if isinstance(value, IrpfSpecialRegime):
            token = value
        elif isinstance(value, str):
            raw = value.strip()
            if not raw:
                raise RegistryValidationError("IRPF special-regime token must be non-empty")
            try:
                token = IrpfSpecialRegime(raw, _registry_validated=True)
            except (TypeError, ValueError) as exc:
                raise RegistryValidationError("IRPF special-regime token must be a non-empty string") from exc
        else:
            raise RegistryValidationError("IRPF special-regime token must be a string token")
        if token not in self.all_special_regimes:
            raise RegistryValidationError(
                f"IRPF special-regime token {str(token)!r} is not declared by fact {_FACT_ID!r}",
            )
        return token

    def special_definition(self, value: object) -> IrpfSpecialRegimeDefinition:
        """Return the declaration for one admitted special regime."""
        token = self.require_special_regime(value)
        return next(item for item in self.special_regimes if item.token == token)


def _optional(entries: Mapping[str, str], key: str) -> str | None:
    value = entries.get(key)
    if value is None or not value.strip():
        return None
    return value.strip()


def _modelos(entries: Mapping[str, str], key: str) -> tuple[str, ...]:
    values = tuple(
        token.strip()
        for token in required_mapping_entry(entries, key, subject=_ENTRY_SUBJECT).split(",")
        if token.strip()
    )
    if not values or len(values) != len(set(values)):
        raise RegistryValidationError(f"IRPF regime vocabulary {key!r} must contain unique filing models")
    return values


def _window_years(entries: Mapping[str, str], key: str) -> int | None:
    raw = _optional(entries, key)
    if raw is None:
        return None
    try:
        value = int(raw)
    except ValueError as exc:
        raise RegistryValidationError(f"IRPF regime vocabulary {key!r} must be an integer") from exc
    if value <= 0:
        raise RegistryValidationError(f"IRPF regime vocabulary {key!r} must be positive")
    return value


_ENTRIES_POLICY = StringMappingPolicy(subject=_ENTRY_SUBJECT, value_whitespace=MappingValueWhitespace.PRESERVE)


_ENTRIES_FACT = StringMappingFact(fact_id=_FACT_ID, date_axis=DateAxis.FILING_PERIOD, policy=_ENTRIES_POLICY)


def resolve_irpf_regime_vocabulary(
    *,
    effective_date: date | None = None,
    authority: GovernedFactSource | None = None,
) -> IrpfRegimeVocabulary:
    """Resolve and validate all five IRPF regime tokens from fact 0125."""
    coordinate = effective_date or today_madrid()
    selected = require_governed_fact_authority(authority, subject=_ENTRY_SUBJECT)
    if selected is governed_facts_in_scope():
        return _scoped_irpf_regime_vocabulary(coordinate)
    with validating_governed_facts(selected):
        return _scoped_irpf_regime_vocabulary(coordinate)


@cache_governed_projection(maxsize=64)
def _scoped_irpf_regime_vocabulary(effective_date: date) -> IrpfRegimeVocabulary:
    """Build the vocabulary once per scoped authority generation and coordinate."""
    entries = _ENTRIES_FACT.resolve_scoped_entries(effective_date=effective_date, authority=None)
    estimation_regimes: list[IrpfEstimationRegimeDefinition] = []
    for raw_token in unique_mapping_tokens(entries, _ESTIMATION_ORDER_KEY, subject=_ENTRY_SUBJECT):
        token = IrpfEstimationRegime(raw_token, _registry_validated=True)
        prefix = f"{_ESTIMATION_PREFIX}{raw_token}."
        if required_mapping_entry(entries, f"{prefix}value", subject=_ENTRY_SUBJECT) != raw_token:
            raise RegistryValidationError(f"IRPF estimation token {raw_token!r} declares a mismatched value")
        estimation_regimes.append(
            IrpfEstimationRegimeDefinition(
                token=token,
                description=required_mapping_entry(entries, f"{prefix}description", subject=_ENTRY_SUBJECT),
                tax_regime=required_mapping_entry(entries, f"{prefix}tax_regime", subject=_ENTRY_SUBJECT),
                filing_modelos=_modelos(entries, f"{prefix}filing_modelos"),
                legal_refs=unique_mapping_legal_refs(entries, f"{prefix}legal_refs", subject=_ENTRY_SUBJECT),
            ),
        )

    vocabulary = IrpfRegimeVocabulary(estimation_regimes=tuple(estimation_regimes), special_regimes=())
    special_regimes: list[IrpfSpecialRegimeDefinition] = []
    for raw_token in unique_mapping_tokens(entries, _SPECIAL_ORDER_KEY, subject=_ENTRY_SUBJECT):
        token = IrpfSpecialRegime(raw_token, _registry_validated=True)
        prefix = f"{_SPECIAL_PREFIX}{raw_token}."
        if required_mapping_entry(entries, f"{prefix}value", subject=_ENTRY_SUBJECT) != raw_token:
            raise RegistryValidationError(f"IRPF special token {raw_token!r} declares a mismatched value")
        special_regimes.append(
            IrpfSpecialRegimeDefinition(
                token=token,
                description=required_mapping_entry(entries, f"{prefix}description", subject=_ENTRY_SUBJECT),
                tax_regime=required_mapping_entry(entries, f"{prefix}tax_regime", subject=_ENTRY_SUBJECT),
                filing_modelos=_modelos(entries, f"{prefix}filing_modelos"),
                window_years=_window_years(entries, f"{prefix}window_years"),
                legal_refs=unique_mapping_legal_refs(entries, f"{prefix}legal_refs", subject=_ENTRY_SUBJECT),
            ),
        )
    return IrpfRegimeVocabulary(
        estimation_regimes=vocabulary.estimation_regimes,
        special_regimes=tuple(special_regimes),
    )


def require_irpf_estimation_regime(
    value: object,
    *,
    effective_date: date | None = None,
    authority: GovernedFactSource | None = None,
) -> IrpfEstimationRegime:
    """Return one registry-declared estimation regime."""
    return resolve_irpf_regime_vocabulary(effective_date=effective_date, authority=authority).require_estimation_regime(
        value,
    )


def require_irpf_special_regime(
    value: object,
    *,
    effective_date: date | None = None,
    authority: GovernedFactSource | None = None,
) -> IrpfSpecialRegime:
    """Return one registry-declared special regime."""
    return resolve_irpf_regime_vocabulary(effective_date=effective_date, authority=authority).require_special_regime(
        value,
    )


def irpf_estimation_regime_tokens(
    *,
    effective_date: date | None = None,
    authority: GovernedFactSource | None = None,
) -> tuple[IrpfEstimationRegime, ...]:
    """Return all estimation-regime tokens in declared order."""
    return tuple(
        item.token
        for item in resolve_irpf_regime_vocabulary(
            effective_date=effective_date, authority=authority
        ).estimation_regimes
    )


def irpf_special_regime_tokens(
    *,
    effective_date: date | None = None,
    authority: GovernedFactSource | None = None,
) -> tuple[IrpfSpecialRegime, ...]:
    """Return all special-regime tokens in declared order."""
    return tuple(
        item.token
        for item in resolve_irpf_regime_vocabulary(effective_date=effective_date, authority=authority).special_regimes
    )


def irpf_estimation_regime_directa_normal_token(
    *,
    effective_date: date | None = None,
    authority: GovernedFactSource | None = None,
) -> IrpfEstimationRegime:
    """Return the declared direct-normal estimation token."""
    return require_irpf_estimation_regime(
        "directa_normal",
        effective_date=effective_date,
        authority=authority,
    )


def irpf_estimation_regime_directa_simplificada_token(
    *,
    effective_date: date | None = None,
    authority: GovernedFactSource | None = None,
) -> IrpfEstimationRegime:
    """Return the declared direct-simplified estimation token."""
    return require_irpf_estimation_regime(
        "directa_simplificada",
        effective_date=effective_date,
        authority=authority,
    )


def irpf_estimation_regime_objetiva_token(
    *,
    effective_date: date | None = None,
    authority: GovernedFactSource | None = None,
) -> IrpfEstimationRegime:
    """Return the declared objective-estimation token."""
    return require_irpf_estimation_regime("objetiva", effective_date=effective_date, authority=authority)


def irpf_special_regime_general_token(
    *,
    effective_date: date | None = None,
    authority: GovernedFactSource | None = None,
) -> IrpfSpecialRegime:
    """Return the declared general special-regime token."""
    return require_irpf_special_regime("general", effective_date=effective_date, authority=authority)


def irpf_special_regime_impatriado_token(
    *,
    effective_date: date | None = None,
    authority: GovernedFactSource | None = None,
) -> IrpfSpecialRegime:
    """Return the declared impatriate special-regime token."""
    return require_irpf_special_regime("impatriado", effective_date=effective_date, authority=authority)


def irpf_special_regime_impatriado_window_years(
    *,
    effective_date: date | None = None,
    authority: GovernedFactSource | None = None,
) -> int:
    """Return the declared duration of the impatriate regime window."""
    definition = resolve_irpf_regime_vocabulary(effective_date=effective_date, authority=authority).special_definition(
        "impatriado",
    )
    if definition.window_years is None:
        raise RegistryValidationError("IRPF impatriado regime does not declare its window length")
    return definition.window_years


__all__ = [
    "IrpfEstimationRegimeDefinition",
    "IrpfRegimeVocabulary",
    "IrpfSpecialRegimeDefinition",
    "irpf_estimation_regime_directa_normal_token",
    "irpf_estimation_regime_directa_simplificada_token",
    "irpf_estimation_regime_objetiva_token",
    "irpf_estimation_regime_tokens",
    "irpf_special_regime_general_token",
    "irpf_special_regime_impatriado_token",
    "irpf_special_regime_impatriado_window_years",
    "irpf_special_regime_tokens",
    "require_irpf_estimation_regime",
    "require_irpf_special_regime",
    "resolve_irpf_regime_vocabulary",
]
