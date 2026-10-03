"""Typed projection of the LIVA capital-goods vocabulary fact (0130)."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date
from typing import TYPE_CHECKING, Final

from ...bienes_inversion.vocabulary import BienInversionDisposalRegime, BienInversionKind
from .errors import RegistryValidationError
from .facts.resolution import required_mapping_entry, unique_mapping_tokens
from .facts.string_mapping import (
    MappingValueWhitespace,
    StringMappingFact,
    StringMappingPolicy,
)
from .schema_base import DateAxis

_ENTRY_SUBJECT: Final = "LIVA capital-goods vocabulary"

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
        """Return capital-goods kinds in registry order."""
        return tuple(item.token for item in self.kinds)

    @property
    def disposal_regime_choices(self) -> tuple[BienInversionDisposalRegime, ...]:
        """Return capital-goods disposal regimes in registry order."""
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
                token = BienInversionKind.from_registry(raw)
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
                token = BienInversionDisposalRegime.from_registry(raw)
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


_ENTRIES_POLICY = StringMappingPolicy(subject=_ENTRY_SUBJECT, value_whitespace=MappingValueWhitespace.PRESERVE)


_ENTRIES_FACT = StringMappingFact(fact_id=_FACT_ID, date_axis=DateAxis.TRANSACTION_DATE, policy=_ENTRIES_POLICY)


def _catalogue(entries: Mapping[str, str]) -> BienInversionCatalogue:
    minimum_year = _minimum_acquisition_year(entries)
    kind_definitions = _kind_definitions(entries)
    disposal_definitions = _disposal_regime_definitions(entries)
    catalogue = _build_catalogue(entries, minimum_year, kind_definitions, disposal_definitions)
    _require_declared_projections(catalogue, kind_definitions, disposal_definitions)
    _require_distinct_projections(catalogue)
    return catalogue


def _minimum_acquisition_year(entries: Mapping[str, str]) -> int:
    try:
        minimum_year = int(required_mapping_entry(entries, _MINIMUM_ACQUISITION_YEAR_KEY, subject=_ENTRY_SUBJECT))
    except ValueError as exc:
        raise RegistryValidationError("LIVA capital-goods minimum acquisition year must be an integer") from exc
    if minimum_year < 1:
        raise RegistryValidationError("LIVA capital-goods minimum acquisition year must be positive")
    return minimum_year


def _kind_definitions(entries: Mapping[str, str]) -> list[BienInversionKindDefinition]:
    kind_definitions: list[BienInversionKindDefinition] = []
    for raw_token in unique_mapping_tokens(entries, _KIND_ORDER_KEY, subject=_ENTRY_SUBJECT):
        token = BienInversionKind.from_registry(raw_token)
        prefix = f"{_KIND_PREFIX}{raw_token}."
        if required_mapping_entry(entries, f"{prefix}value", subject=_ENTRY_SUBJECT) != raw_token:
            raise RegistryValidationError(f"bien-inversion kind {raw_token!r} declares a mismatched value")
        kind_definitions.append(
            BienInversionKindDefinition(
                token=token,
                description=required_mapping_entry(entries, f"{prefix}description", subject=_ENTRY_SUBJECT),
                legal_refs=unique_mapping_tokens(entries, f"{prefix}legal_refs", subject=_ENTRY_SUBJECT),
            ),
        )
    if len({item.token for item in kind_definitions}) != len(kind_definitions):
        raise RegistryValidationError("LIVA capital-goods vocabulary contains duplicate kinds")
    return kind_definitions


def _disposal_regime_definitions(entries: Mapping[str, str]) -> list[BienInversionDisposalRegimeDefinition]:
    disposal_definitions: list[BienInversionDisposalRegimeDefinition] = []
    for raw_token in unique_mapping_tokens(entries, _DISPOSAL_REGIME_ORDER_KEY, subject=_ENTRY_SUBJECT):
        token = BienInversionDisposalRegime.from_registry(raw_token)
        prefix = f"{_DISPOSAL_REGIME_PREFIX}{raw_token}."
        if required_mapping_entry(entries, f"{prefix}value", subject=_ENTRY_SUBJECT) != raw_token:
            raise RegistryValidationError(f"bien-inversion disposal regime {raw_token!r} declares a mismatched value")
        disposal_definitions.append(
            BienInversionDisposalRegimeDefinition(
                token=token,
                description=required_mapping_entry(entries, f"{prefix}description", subject=_ENTRY_SUBJECT),
                legal_refs=unique_mapping_tokens(entries, f"{prefix}legal_refs", subject=_ENTRY_SUBJECT),
            ),
        )
    if len({item.token for item in disposal_definitions}) != len(disposal_definitions):
        raise RegistryValidationError("LIVA capital-goods vocabulary contains duplicate disposal regimes")
    return disposal_definitions


def _build_catalogue(
    entries: Mapping[str, str],
    minimum_year: int,
    kind_definitions: list[BienInversionKindDefinition],
    disposal_definitions: list[BienInversionDisposalRegimeDefinition],
) -> BienInversionCatalogue:
    catalogue = BienInversionCatalogue(
        declarations=entries,
        minimum_acquisition_year=minimum_year,
        kinds=tuple(kind_definitions),
        disposal_regimes=tuple(disposal_definitions),
        real_estate_kind=BienInversionKind.from_registry(
            required_mapping_entry(entries, _KIND_REAL_ESTATE_KEY, subject=_ENTRY_SUBJECT)
        ),
        non_real_estate_kind=BienInversionKind.from_registry(
            required_mapping_entry(entries, _KIND_NON_REAL_ESTATE_KEY, subject=_ENTRY_SUBJECT)
        ),
        subject_not_exempt_regime=BienInversionDisposalRegime.from_registry(
            required_mapping_entry(entries, _DISPOSAL_REGIME_SUBJECT_NOT_EXEMPT_KEY, subject=_ENTRY_SUBJECT),
        ),
        exempt_or_outside_scope_regime=BienInversionDisposalRegime.from_registry(
            required_mapping_entry(entries, _DISPOSAL_REGIME_EXEMPT_OR_OUTSIDE_SCOPE_KEY, subject=_ENTRY_SUBJECT),
        ),
    )
    return catalogue


def _require_declared_projections(
    catalogue: BienInversionCatalogue,
    kind_definitions: list[BienInversionKindDefinition],
    disposal_definitions: list[BienInversionDisposalRegimeDefinition],
) -> None:
    _require_ordered_kind_projections(catalogue, kind_definitions)
    _require_ordered_disposal_projections(catalogue, disposal_definitions)
    _require_kind_role_projections(catalogue)
    _require_disposal_role_projections(catalogue)


def _require_ordered_kind_projections(
    catalogue: BienInversionCatalogue,
    definitions: list[BienInversionKindDefinition],
) -> None:
    if set(catalogue.kind_choices) != {item.token for item in definitions}:
        raise RegistryValidationError("LIVA capital-goods kind projections must be declared in kind.order")


def _require_ordered_disposal_projections(
    catalogue: BienInversionCatalogue,
    definitions: list[BienInversionDisposalRegimeDefinition],
) -> None:
    if set(catalogue.disposal_regime_choices) != {item.token for item in definitions}:
        raise RegistryValidationError(
            "LIVA capital-goods disposal projections must be declared in disposal_regime.order"
        )


def _require_kind_role_projections(catalogue: BienInversionCatalogue) -> None:
    if catalogue.real_estate_kind not in catalogue.kind_choices:
        raise RegistryValidationError("real-estate kind projection is not declared in kind.order")
    if catalogue.non_real_estate_kind not in catalogue.kind_choices:
        raise RegistryValidationError("non-real-estate kind projection is not declared in kind.order")


def _require_disposal_role_projections(catalogue: BienInversionCatalogue) -> None:
    if catalogue.subject_not_exempt_regime not in catalogue.disposal_regime_choices:
        raise RegistryValidationError("subject-not-exempt projection is not declared in disposal_regime.order")
    if catalogue.exempt_or_outside_scope_regime not in catalogue.disposal_regime_choices:
        raise RegistryValidationError("exempt-or-outside-scope projection is not declared in disposal_regime.order")


def _require_distinct_projections(catalogue: BienInversionCatalogue) -> None:
    if catalogue.real_estate_kind == catalogue.non_real_estate_kind:
        raise RegistryValidationError("capital-goods kind projections must be distinct")
    if catalogue.subject_not_exempt_regime == catalogue.exempt_or_outside_scope_regime:
        raise RegistryValidationError("capital-goods disposal regime projections must be distinct")


def resolve_bienes_inversion_catalogue(
    *,
    effective_date: date | None = None,
    authority: ValidatedRegistryAuthority | None = None,
) -> BienInversionCatalogue:
    """Resolve the selected transaction-date LIVA capital-goods vocabulary.

    Core types:
    :class:`~cadrumo.domain.calculations.registry.authority.ValidatedRegistryAuthority`.
    """
    return _catalogue(_ENTRIES_FACT.resolve_scoped_entries(effective_date=effective_date, authority=authority))


def require_bien_inversion_kind(
    value: object,
    *,
    effective_date: date | None = None,
    authority: ValidatedRegistryAuthority | None = None,
) -> BienInversionKind:
    """Validate one value against the dated capital-goods kind vocabulary.

    Core types:
    :class:`~cadrumo.domain.calculations.registry.authority.ValidatedRegistryAuthority`.
    """
    return resolve_bienes_inversion_catalogue(effective_date=effective_date, authority=authority).require_kind(value)


def require_bien_inversion_disposal_regime(
    value: object,
    *,
    effective_date: date | None = None,
    authority: ValidatedRegistryAuthority | None = None,
) -> BienInversionDisposalRegime:
    """Validate one value against the dated disposal-regime vocabulary.

    Core types:
    :class:`~cadrumo.domain.calculations.registry.authority.ValidatedRegistryAuthority`.
    """
    return resolve_bienes_inversion_catalogue(
        effective_date=effective_date,
        authority=authority,
    ).require_disposal_regime(value)


def bien_inversion_disposal_regime_choices(
    *,
    effective_date: date | None = None,
    authority: ValidatedRegistryAuthority | None = None,
) -> tuple[BienInversionDisposalRegime, ...]:
    """Return disposal-regime choices in registry order.

    Core types:
    :class:`~cadrumo.domain.calculations.registry.authority.ValidatedRegistryAuthority`.
    """
    return resolve_bienes_inversion_catalogue(
        effective_date=effective_date,
        authority=authority,
    ).disposal_regime_choices


def minimum_bien_inversion_acquisition_year(
    *,
    effective_date: date | None = None,
    authority: ValidatedRegistryAuthority | None = None,
) -> int:
    """Return the registry-declared minimum capital-goods acquisition year.

    Core types:
    :class:`~cadrumo.domain.calculations.registry.authority.ValidatedRegistryAuthority`.
    """
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
    """Test a capital-goods kind against a named registry projection.

    Core types:
    :class:`~cadrumo.domain.calculations.registry.authority.ValidatedRegistryAuthority`.
    """
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
    """Test a disposal regime against a named registry projection.

    Core types:
    :class:`~cadrumo.domain.calculations.registry.authority.ValidatedRegistryAuthority`.
    """
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
    "is_bien_inversion_disposal_regime",
    "is_bien_inversion_kind",
    "minimum_bien_inversion_acquisition_year",
    "require_bien_inversion_disposal_regime",
    "require_bien_inversion_kind",
    "resolve_bienes_inversion_catalogue",
]
