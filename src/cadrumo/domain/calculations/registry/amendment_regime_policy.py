"""Typed projection of the registry-owned amendment-regime policy fact."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date
from types import MappingProxyType
from typing import TYPE_CHECKING

from ....core.amendment_kind_regime import (
    AmendmentKindRegime,
    AmendmentRegimePolicy,
    resolve_amendment_kind_regime,
)
from ....core.period import Period
from .errors import RegistryValidationError
from .facts.resolution import MappingFactQuery, ResolvedMappingFact
from .governed_fact_scope import GovernedFactSource, cache_governed_projection, governed_facts_in_scope
from .schema_base import DateAxis

if TYPE_CHECKING:
    from .authority import ValidatedRegistryAuthority


_FACT_ID = "amendment-regime-policy"
_PROCEDURE_ORDER_KEY = "procedure.order"
_PRE_ORDER_KEY = "regime.pre_order"
_POST_ORDER_KEY = "regime.post_order"
_BOUNDARY_ORDER_KEY = "boundary.order"


def _required(entries: Mapping[str, str], key: str) -> str:
    value = entries.get(key)
    if value is None or not value.strip():
        raise RegistryValidationError(f"amendment-regime-policy is missing {key!r}")
    return value.strip()


def _csv(entries: Mapping[str, str], key: str) -> tuple[str, ...]:
    values = tuple(token.strip() for token in _required(entries, key).split(",") if token.strip())
    if not values or len(values) != len(set(values)):
        raise RegistryValidationError(f"amendment-regime-policy {key!r} must contain unique tokens")
    return values


def _mapping_entries(resolved: ResolvedMappingFact) -> Mapping[str, str]:
    entries: dict[str, str] = {}
    for entry in resolved.payload.entries:
        if not isinstance(entry.key, str) or not isinstance(entry.value, str):
            raise RegistryValidationError("amendment-regime-policy entries must be string-to-string")
        if entry.key in entries:
            raise RegistryValidationError(f"duplicate amendment-regime-policy key {entry.key!r}")
        entries[entry.key] = entry.value.strip()
    return MappingProxyType(entries)


def _resolve_entries(*, effective_date: date, authority: GovernedFactSource) -> Mapping[str, str]:
    resolved = authority.resolve_governed_fact(
        MappingFactQuery(
            fact_id=_FACT_ID,
            date_axis=DateAxis.FILING_PERIOD,
            effective_date=effective_date,
        ),
    )
    if not isinstance(resolved, ResolvedMappingFact):
        raise RegistryValidationError("amendment-regime-policy must resolve as a mapping fact")
    return _mapping_entries(resolved)


@cache_governed_projection(maxsize=64)
def _bundled_mapping_entries(effective_date: date) -> Mapping[str, str]:
    del effective_date
    raise RegistryValidationError("amendment-regime policy requires an explicit authority operation or scope")


def _selected_mapping_entries(
    *,
    effective_date: date,
    authority: ValidatedRegistryAuthority | None,
) -> Mapping[str, str]:
    selected = authority or governed_facts_in_scope()
    if selected is None:
        return _bundled_mapping_entries(effective_date)
    return _resolve_entries(effective_date=effective_date, authority=selected)


def _policy(entries: Mapping[str, str]) -> AmendmentRegimePolicy:
    procedure_order = _csv(entries, _PROCEDURE_ORDER_KEY)
    for token in procedure_order:
        if _required(entries, f"procedure.{token}.value") != token:
            raise RegistryValidationError(
                f"amendment-regime-policy procedure {token!r} declares a mismatched value",
            )

    pre_order = _csv(entries, _PRE_ORDER_KEY)
    post_order = _csv(entries, _POST_ORDER_KEY)
    declared_procedures = frozenset(procedure_order)
    if not set(pre_order).issubset(declared_procedures):
        raise RegistryValidationError("amendment-regime-policy pre-regime uses an undeclared procedure")
    if not set(post_order).issubset(declared_procedures):
        raise RegistryValidationError("amendment-regime-policy post-regime uses an undeclared procedure")

    boundary_models = _csv(entries, _BOUNDARY_ORDER_KEY)
    boundaries: dict[str, date] = {}
    for modelo in boundary_models:
        try:
            boundaries[modelo] = date.fromisoformat(_required(entries, f"boundary.{modelo}.date"))
        except ValueError as exc:
            raise RegistryValidationError(
                f"amendment-regime-policy boundary for {modelo!r} must be an ISO date",
            ) from exc
        if not (entries.get(f"boundary.{modelo}.source_fact") or entries.get(f"boundary.{modelo}.source")):
            raise RegistryValidationError(
                f"amendment-regime-policy boundary for {modelo!r} lacks source evidence",
            )
    if len(boundaries) != 3:
        raise RegistryValidationError("amendment-regime-policy must declare the complete three-model boundary set")

    return AmendmentRegimePolicy(
        rectificativa_effective_from=MappingProxyType(boundaries),
        pre_rectificativa_kinds=frozenset(pre_order),
        post_rectificativa_kinds=frozenset(post_order),
    )


@cache_governed_projection(maxsize=64)
def _bundled_policy(effective_date: date) -> AmendmentRegimePolicy:
    return _policy(_bundled_mapping_entries(effective_date))


def resolve_amendment_regime_policy(
    *,
    effective_date: date | None = None,
    authority: ValidatedRegistryAuthority | None = None,
) -> AmendmentRegimePolicy:
    """Resolve the selected dated amendment policy, failing closed if absent."""
    coordinate = effective_date or date.today()
    if authority is None and governed_facts_in_scope() is None:
        return _bundled_policy(coordinate)
    return _policy(_selected_mapping_entries(effective_date=coordinate, authority=authority))


def resolve_amendment_regime_policy_for_period(
    period: Period,
    *,
    authority: ValidatedRegistryAuthority | None = None,
) -> AmendmentRegimePolicy:
    """Resolve amendment policy at the period's filing-period coordinate."""
    effective_date = period.end_date if period.has_date_span() else date(period.filing_year, 12, 31)
    return resolve_amendment_regime_policy(effective_date=effective_date, authority=authority)


def resolve_amendment_kind_regime_for_period(
    modelo: str,
    period: Period,
    *,
    authority: ValidatedRegistryAuthority | None = None,
) -> AmendmentKindRegime:
    """Resolve a model/period amendment regime through the selected fact."""
    return resolve_amendment_kind_regime(
        modelo,
        period,
        policy=resolve_amendment_regime_policy_for_period(period, authority=authority),
    )


def permitted_amendment_kind_values_for_period(
    modelo: str,
    period: Period,
    *,
    authority: ValidatedRegistryAuthority | None = None,
) -> frozenset[str]:
    """Return permitted amendment kinds from the registry-projected policy."""
    return resolve_amendment_kind_regime_for_period(modelo, period, authority=authority).permitted_kinds


__all__ = [
    "permitted_amendment_kind_values_for_period",
    "resolve_amendment_kind_regime_for_period",
    "resolve_amendment_regime_policy",
    "resolve_amendment_regime_policy_for_period",
]
