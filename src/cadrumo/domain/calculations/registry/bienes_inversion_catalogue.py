"""Typed projection of the LIVA capital-goods vocabulary fact (0130)."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date
from types import MappingProxyType
from typing import TYPE_CHECKING

from ...bienes_inversion.vocabulary import BienInversionDisposalRegime, BienInversionKind
from .errors import RegistryValidationError
from .facts.resolution import MappingFactQuery, ResolvedMappingFact
from .governed_fact_scope import GovernedFactSource, cache_governed_projection, governed_facts_in_scope
from .schema_base import DateAxis

if TYPE_CHECKING:
    from .authority import ValidatedRegistryAuthority


_FACT_ID = "liva-bienes-inversion-vocabulary"
_MINIMUM_ACQUISITION_YEAR_KEY = "acquisition.minimum_year"
_KIND_ORDER_KEY = "kind.order"
_KIND_REAL_ESTATE_KEY = "kind.real_estate_token"
_KIND_NON_REAL_ESTATE_KEY = "kind.non_real_estate_token"
_KIND_PREFIX = "kind."
_DISPOSAL_REGIME_ORDER_KEY = "disposal_regime.order"
_DISPOSAL_REGIME_SUBJECT_NOT_EXEMPT_KEY = "disposal_regime.subject_not_exempt_token"
_DISPOSAL_REGIME_EXEMPT_OR_OUTSIDE_SCOPE_KEY = "disposal_regime.exempt_or_outside_scope_token"
_DISPOSAL_REGIME_PREFIX = "disposal_regime."


@dataclass(frozen=True, slots=True)
class BienInversionKindDefinition:
    """One registry-declared capital-goods kind and its legal semantics."""

    token: BienInversionKind
    description: str
    legal_refs: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class BienInversionDisposalRegimeDefinition:
    """One registry-declared disposal regime and its legal semantics."""

    token: BienInversionDisposalRegime
    description: str
    legal_refs: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class BienInversionCatalogue:
    """Complete typed projection of fact 0130."""

    declarations: Mapping[str, str]
    minimum_acquisition_year: int
    kinds: tuple[BienInversionKindDefinition, ...]
    disposal_regimes: tuple[BienInversionDisposalRegimeDefinition, ...]
    real_estate_kind: BienInversionKind
    non_real_estate_kind: BienInversionKind
    subject_not_exempt_regime: BienInversionDisposalRegime
    exempt_or_outside_scope_regime: BienInversionDisposalRegime

    @property
    def kind_choices(self) -> tuple[BienInversionKind, ...]:
        return tuple(item.token for item in self.kinds)

    @property
    def disposal_regime_choices(self) -> tuple[BienInversionDisposalRegime, ...]:
        return tuple(item.token for item in self.disposal_regimes)

    def require_kind(self, value: object) -> BienInversionKind:
        """Project a kind only when the selected dated fact declares it."""
        if isinstance(value, BienInversionKind):
            token = value
        elif isinstance(value, str):
            raw = value.strip()
            if not raw:
                raise RegistryValidationError("bien-inversion kind must be a non-empty string token")
            try:
                token = BienInversionKind._from_registry(raw)
            except (TypeError, ValueError) as exc:
                raise RegistryValidationError("bien-inversion kind must be a non-empty string token") from exc
        else:
            raise RegistryValidationError("bien-inversion kind must be a string token")
        if token not in self.kind_choices:
            raise RegistryValidationError(
                f"bien-inversion kind {str(token)!r} is not declared by fact {_FACT_ID!r}",
            )
        return token

    def require_disposal_regime(self, value: object) -> BienInversionDisposalRegime:
        """Project a disposal regime only when fact 0130 declares it."""
        if isinstance(value, BienInversionDisposalRegime):
            token = value
        elif isinstance(value, str):
            raw = value.strip()
            if not raw:
                raise RegistryValidationError("bien-inversion disposal regime must be a non-empty string token")
            try:
                token = BienInversionDisposalRegime._from_registry(raw)
            except (TypeError, ValueError) as exc:
                raise RegistryValidationError(
                    "bien-inversion disposal regime must be a non-empty string token",
                ) from exc
        else:
            raise RegistryValidationError("bien-inversion disposal regime must be a string token")
        if token not in self.disposal_regime_choices:
            raise RegistryValidationError(
                f"bien-inversion disposal regime {str(token)!r} is not declared by fact {_FACT_ID!r}",
            )
        return token

    def is_real_estate_kind(self, value: object) -> bool:
        return self.require_kind(value) == self.real_estate_kind

    def is_subject_not_exempt_regime(self, value: object) -> bool:
        return self.require_disposal_regime(value) == self.subject_not_exempt_regime


def _required(entries: Mapping[str, str], key: str) -> str:
    value = entries.get(key)
    if value is None or not value.strip():
        raise RegistryValidationError(f"LIVA capital-goods vocabulary is missing {key!r}")
    return value.strip()


def _csv(entries: Mapping[str, str], key: str) -> tuple[str, ...]:
    values = tuple(token.strip() for token in _required(entries, key).split(",") if token.strip())
    if not values or len(values) != len(set(values)):
        raise RegistryValidationError(f"LIVA capital-goods vocabulary {key!r} must contain unique tokens")
    return values


def _refs(entries: Mapping[str, str], key: str) -> tuple[str, ...]:
    values = _csv(entries, key)
    if not values:
        raise RegistryValidationError(f"LIVA capital-goods vocabulary {key!r} must contain legal references")
    return values


def _mapping_entries(resolved: ResolvedMappingFact) -> Mapping[str, str]:
    entries: dict[str, str] = {}
    for entry in resolved.payload.entries:
        if not isinstance(entry.key, str) or not isinstance(entry.value, str):
            raise RegistryValidationError("LIVA capital-goods vocabulary entries must be string-to-string")
        if entry.key in entries:
            raise RegistryValidationError(f"duplicate LIVA capital-goods vocabulary key {entry.key!r}")
        entries[entry.key] = entry.value
    return MappingProxyType(entries)


def _resolve_entries(*, effective_date: date, authority: GovernedFactSource) -> Mapping[str, str]:
    resolved = authority.resolve_governed_fact(
        MappingFactQuery(
            fact_id=_FACT_ID,
            date_axis=DateAxis.TRANSACTION_DATE,
            effective_date=effective_date,
        ),
    )
    if not isinstance(resolved, ResolvedMappingFact):
        raise RegistryValidationError("LIVA capital-goods vocabulary must resolve as a mapping fact")
    return _mapping_entries(resolved)


@cache_governed_projection(maxsize=64)
def _bundled_mapping_entries(effective_date: date) -> Mapping[str, str]:
    from .authority import bundled_authority

    return _resolve_entries(effective_date=effective_date, authority=(governed_facts_in_scope() or bundled_authority()))


def _selected_mapping_entries(
    *,
    effective_date: date | None,
    authority: ValidatedRegistryAuthority | None,
) -> Mapping[str, str]:
    coordinate = effective_date or date.today()
    selected = authority or governed_facts_in_scope()
    if selected is None:
        return _bundled_mapping_entries(coordinate)
    return _resolve_entries(effective_date=coordinate, authority=selected)


def _catalogue(entries: Mapping[str, str]) -> BienInversionCatalogue:
    try:
        minimum_year = int(_required(entries, _MINIMUM_ACQUISITION_YEAR_KEY))
    except ValueError as exc:
        raise RegistryValidationError("LIVA capital-goods minimum acquisition year must be an integer") from exc
    if minimum_year < 1:
        raise RegistryValidationError("LIVA capital-goods minimum acquisition year must be positive")

    kind_definitions: list[BienInversionKindDefinition] = []
    for raw_token in _csv(entries, _KIND_ORDER_KEY):
        token = BienInversionKind._from_registry(raw_token)
        prefix = f"{_KIND_PREFIX}{raw_token}."
        if _required(entries, f"{prefix}value") != raw_token:
            raise RegistryValidationError(f"bien-inversion kind {raw_token!r} declares a mismatched value")
        kind_definitions.append(
            BienInversionKindDefinition(
                token=token,
                description=_required(entries, f"{prefix}description"),
                legal_refs=_refs(entries, f"{prefix}legal_refs"),
            ),
        )
    if len({item.token for item in kind_definitions}) != len(kind_definitions):
        raise RegistryValidationError("LIVA capital-goods vocabulary contains duplicate kinds")

    disposal_definitions: list[BienInversionDisposalRegimeDefinition] = []
    for raw_token in _csv(entries, _DISPOSAL_REGIME_ORDER_KEY):
        token = BienInversionDisposalRegime._from_registry(raw_token)
        prefix = f"{_DISPOSAL_REGIME_PREFIX}{raw_token}."
        if _required(entries, f"{prefix}value") != raw_token:
            raise RegistryValidationError(f"bien-inversion disposal regime {raw_token!r} declares a mismatched value")
        disposal_definitions.append(
            BienInversionDisposalRegimeDefinition(
                token=token,
                description=_required(entries, f"{prefix}description"),
                legal_refs=_refs(entries, f"{prefix}legal_refs"),
            ),
        )
    if len({item.token for item in disposal_definitions}) != len(disposal_definitions):
        raise RegistryValidationError("LIVA capital-goods vocabulary contains duplicate disposal regimes")

    catalogue = BienInversionCatalogue(
        declarations=entries,
        minimum_acquisition_year=minimum_year,
        kinds=tuple(kind_definitions),
        disposal_regimes=tuple(disposal_definitions),
        real_estate_kind=BienInversionKind._from_registry(_required(entries, _KIND_REAL_ESTATE_KEY)),
        non_real_estate_kind=BienInversionKind._from_registry(_required(entries, _KIND_NON_REAL_ESTATE_KEY)),
        subject_not_exempt_regime=BienInversionDisposalRegime._from_registry(
            _required(entries, _DISPOSAL_REGIME_SUBJECT_NOT_EXEMPT_KEY),
        ),
        exempt_or_outside_scope_regime=BienInversionDisposalRegime._from_registry(
            _required(entries, _DISPOSAL_REGIME_EXEMPT_OR_OUTSIDE_SCOPE_KEY),
        ),
    )
    if set(catalogue.kind_choices) != {item.token for item in kind_definitions}:
        raise RegistryValidationError("LIVA capital-goods kind projections must be declared in kind.order")
    if set(catalogue.disposal_regime_choices) != {item.token for item in disposal_definitions}:
        raise RegistryValidationError(
            "LIVA capital-goods disposal projections must be declared in disposal_regime.order"
        )
    if catalogue.real_estate_kind not in catalogue.kind_choices:
        raise RegistryValidationError("real-estate kind projection is not declared in kind.order")
    if catalogue.non_real_estate_kind not in catalogue.kind_choices:
        raise RegistryValidationError("non-real-estate kind projection is not declared in kind.order")
    if catalogue.subject_not_exempt_regime not in catalogue.disposal_regime_choices:
        raise RegistryValidationError("subject-not-exempt projection is not declared in disposal_regime.order")
    if catalogue.exempt_or_outside_scope_regime not in catalogue.disposal_regime_choices:
        raise RegistryValidationError("exempt-or-outside-scope projection is not declared in disposal_regime.order")
    if catalogue.real_estate_kind == catalogue.non_real_estate_kind:
        raise RegistryValidationError("capital-goods kind projections must be distinct")
    if catalogue.subject_not_exempt_regime == catalogue.exempt_or_outside_scope_regime:
        raise RegistryValidationError("capital-goods disposal regime projections must be distinct")
    return catalogue


@cache_governed_projection(maxsize=64)
def _bundled_catalogue(effective_date: date) -> BienInversionCatalogue:
    return _catalogue(_bundled_mapping_entries(effective_date))


def resolve_bienes_inversion_catalogue(
    *,
    effective_date: date | None = None,
    authority: ValidatedRegistryAuthority | None = None,
) -> BienInversionCatalogue:
    """Resolve the selected transaction-date LIVA capital-goods vocabulary."""
    coordinate = effective_date or date.today()
    if authority is None and governed_facts_in_scope() is None:
        return _bundled_catalogue(coordinate)
    return _catalogue(_selected_mapping_entries(effective_date=coordinate, authority=authority))


def require_bien_inversion_kind(
    value: object,
    *,
    effective_date: date | None = None,
    authority: ValidatedRegistryAuthority | None = None,
) -> BienInversionKind:
    return resolve_bienes_inversion_catalogue(effective_date=effective_date, authority=authority).require_kind(value)


def bien_inversion_kind_choices(
    *,
    effective_date: date | None = None,
    authority: ValidatedRegistryAuthority | None = None,
) -> tuple[BienInversionKind, ...]:
    return resolve_bienes_inversion_catalogue(
        effective_date=effective_date,
        authority=authority,
    ).kind_choices


def require_bien_inversion_disposal_regime(
    value: object,
    *,
    effective_date: date | None = None,
    authority: ValidatedRegistryAuthority | None = None,
) -> BienInversionDisposalRegime:
    return resolve_bienes_inversion_catalogue(
        effective_date=effective_date,
        authority=authority,
    ).require_disposal_regime(value)


def bien_inversion_disposal_regime_choices(
    *,
    effective_date: date | None = None,
    authority: ValidatedRegistryAuthority | None = None,
) -> tuple[BienInversionDisposalRegime, ...]:
    return resolve_bienes_inversion_catalogue(
        effective_date=effective_date,
        authority=authority,
    ).disposal_regime_choices


def minimum_bien_inversion_acquisition_year(
    *,
    effective_date: date | None = None,
    authority: ValidatedRegistryAuthority | None = None,
) -> int:
    return resolve_bienes_inversion_catalogue(
        effective_date=effective_date,
        authority=authority,
    ).minimum_acquisition_year


def is_bien_inversion_kind(
    value: object,
    projection: str,
    *,
    effective_date: date | None = None,
    authority: ValidatedRegistryAuthority | None = None,
) -> bool:
    catalogue = resolve_bienes_inversion_catalogue(effective_date=effective_date, authority=authority)
    token = catalogue.require_kind(value)
    if projection == _KIND_REAL_ESTATE_KEY:
        return token == catalogue.real_estate_kind
    if projection == _KIND_NON_REAL_ESTATE_KEY:
        return token == catalogue.non_real_estate_kind
    raise RegistryValidationError(f"unknown LIVA capital-goods kind projection {projection!r}")


def is_bien_inversion_disposal_regime(
    value: object,
    projection: str,
    *,
    effective_date: date | None = None,
    authority: ValidatedRegistryAuthority | None = None,
) -> bool:
    catalogue = resolve_bienes_inversion_catalogue(effective_date=effective_date, authority=authority)
    token = catalogue.require_disposal_regime(value)
    if projection == _DISPOSAL_REGIME_SUBJECT_NOT_EXEMPT_KEY:
        return token == catalogue.subject_not_exempt_regime
    if projection == _DISPOSAL_REGIME_EXEMPT_OR_OUTSIDE_SCOPE_KEY:
        return token == catalogue.exempt_or_outside_scope_regime
    raise RegistryValidationError(f"unknown LIVA capital-goods disposal projection {projection!r}")


__all__ = [
    "BienInversionCatalogue",
    "BienInversionDisposalRegimeDefinition",
    "BienInversionKindDefinition",
    "bien_inversion_disposal_regime_choices",
    "bien_inversion_kind_choices",
    "is_bien_inversion_disposal_regime",
    "is_bien_inversion_kind",
    "minimum_bien_inversion_acquisition_year",
    "require_bien_inversion_disposal_regime",
    "require_bien_inversion_kind",
    "resolve_bienes_inversion_catalogue",
]
