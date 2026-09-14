"""Typed projections for the dated IRPF regime vocabulary fact."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date
from types import MappingProxyType

from ...deadlines.models import IrpfEstimationRegime, IrpfSpecialRegime
from .errors import RegistryValidationError
from .facts.resolution import MappingFactQuery, ResolvedMappingFact
from .governed_fact_scope import GovernedFactSource, cache_governed_projection, governed_facts_in_scope
from .schema_base import DateAxis

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

    def estimation_definition(self, value: object) -> IrpfEstimationRegimeDefinition:
        """Return the declaration for one admitted estimation regime."""
        token = self.require_estimation_regime(value)
        return next(item for item in self.estimation_regimes if item.token == token)

    def special_definition(self, value: object) -> IrpfSpecialRegimeDefinition:
        """Return the declaration for one admitted special regime."""
        token = self.require_special_regime(value)
        return next(item for item in self.special_regimes if item.token == token)


def _required(entries: Mapping[str, str], key: str) -> str:
    value = entries.get(key)
    if value is None or not value.strip():
        raise RegistryValidationError(f"IRPF regime vocabulary is missing {key!r}")
    return value.strip()


def _optional(entries: Mapping[str, str], key: str) -> str | None:
    value = entries.get(key)
    if value is None or not value.strip():
        return None
    return value.strip()


def _csv(entries: Mapping[str, str], key: str) -> tuple[str, ...]:
    values = tuple(token.strip() for token in _required(entries, key).split(",") if token.strip())
    if not values or len(values) != len(set(values)):
        raise RegistryValidationError(f"IRPF regime vocabulary {key!r} must contain unique tokens")
    return values


def _refs(entries: Mapping[str, str], key: str) -> tuple[str, ...]:
    values = tuple(token.strip() for token in _required(entries, key).split(",") if token.strip())
    if not values or len(values) != len(set(values)):
        raise RegistryValidationError(f"IRPF regime vocabulary {key!r} must contain unique legal references")
    return values


def _modelos(entries: Mapping[str, str], key: str) -> tuple[str, ...]:
    values = tuple(token.strip() for token in _required(entries, key).split(",") if token.strip())
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


def _mapping_entries(resolved: ResolvedMappingFact) -> Mapping[str, str]:
    entries: dict[str, str] = {}
    for entry in resolved.payload.entries:
        if not isinstance(entry.key, str) or not isinstance(entry.value, str):
            raise RegistryValidationError("IRPF regime vocabulary entries must be string-to-string")
        if entry.key in entries:
            raise RegistryValidationError(f"duplicate IRPF regime vocabulary key {entry.key!r}")
        entries[entry.key] = entry.value
    return MappingProxyType(entries)


def _resolve_mapping_entries(
    *,
    effective_date: date,
    authority: GovernedFactSource,
) -> Mapping[str, str]:
    resolved = authority.resolve_governed_fact(
        MappingFactQuery(
            fact_id=_FACT_ID,
            date_axis=DateAxis.FILING_PERIOD,
            effective_date=effective_date,
        ),
    )
    if not isinstance(resolved, ResolvedMappingFact):
        raise RegistryValidationError("IRPF regime vocabulary must resolve as a mapping fact")
    return _mapping_entries(resolved)


@cache_governed_projection(maxsize=64)
def _bundled_mapping_entries(effective_date: date) -> Mapping[str, str]:
    del effective_date
    raise RegistryValidationError("IRPF regime catalogue requires an explicit authority operation or scope")


def _selected_mapping_entries(
    *,
    effective_date: date | None,
    authority: GovernedFactSource | None,
) -> Mapping[str, str]:
    coordinate = effective_date or date.today()
    selected = authority or governed_facts_in_scope()
    if selected is None:
        return _bundled_mapping_entries(coordinate)
    return _resolve_mapping_entries(effective_date=coordinate, authority=selected)


def resolve_irpf_regime_vocabulary(
    *,
    effective_date: date | None = None,
    authority: GovernedFactSource | None = None,
) -> IrpfRegimeVocabulary:
    """Resolve and validate all five IRPF regime tokens from fact 0125."""
    entries = _selected_mapping_entries(effective_date=effective_date, authority=authority)
    estimation_regimes: list[IrpfEstimationRegimeDefinition] = []
    for raw_token in _csv(entries, _ESTIMATION_ORDER_KEY):
        token = IrpfEstimationRegime(raw_token, _registry_validated=True)
        prefix = f"{_ESTIMATION_PREFIX}{raw_token}."
        if _required(entries, f"{prefix}value") != raw_token:
            raise RegistryValidationError(f"IRPF estimation token {raw_token!r} declares a mismatched value")
        estimation_regimes.append(
            IrpfEstimationRegimeDefinition(
                token=token,
                description=_required(entries, f"{prefix}description"),
                tax_regime=_required(entries, f"{prefix}tax_regime"),
                filing_modelos=_modelos(entries, f"{prefix}filing_modelos"),
                legal_refs=_refs(entries, f"{prefix}legal_refs"),
            ),
        )

    vocabulary = IrpfRegimeVocabulary(estimation_regimes=tuple(estimation_regimes), special_regimes=())
    special_regimes: list[IrpfSpecialRegimeDefinition] = []
    for raw_token in _csv(entries, _SPECIAL_ORDER_KEY):
        token = IrpfSpecialRegime(raw_token, _registry_validated=True)
        prefix = f"{_SPECIAL_PREFIX}{raw_token}."
        if _required(entries, f"{prefix}value") != raw_token:
            raise RegistryValidationError(f"IRPF special token {raw_token!r} declares a mismatched value")
        special_regimes.append(
            IrpfSpecialRegimeDefinition(
                token=token,
                description=_required(entries, f"{prefix}description"),
                tax_regime=_required(entries, f"{prefix}tax_regime"),
                filing_modelos=_modelos(entries, f"{prefix}filing_modelos"),
                window_years=_window_years(entries, f"{prefix}window_years"),
                legal_refs=_refs(entries, f"{prefix}legal_refs"),
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
