"""Typed projection of the registry-owned amendment-regime policy fact."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date
from types import MappingProxyType
from typing import TYPE_CHECKING, Final

from ....core.amendment_kind_regime import (
    AmendmentKindRegime,
    AmendmentRegimePolicy,
    resolve_amendment_kind_regime,
)
from ....core.period import Period
from .errors import RegistryValidationError
from .facts.resolution import required_mapping_entry, unique_mapping_tokens
from .facts.string_mapping import (
    MappingValueWhitespace,
    StringMappingFact,
    StringMappingPolicy,
)
from .schema_base import DateAxis

_ENTRY_SUBJECT: Final = "amendment-regime-policy"

if TYPE_CHECKING:
    from .authority import ValidatedRegistryAuthority


_FACT_ID = "amendment-regime-policy"
_PROCEDURE_ORDER_KEY = "procedure.order"
_PRE_ORDER_KEY = "regime.pre_order"
_POST_ORDER_KEY = "regime.post_order"
_BOUNDARY_ORDER_KEY = "boundary.order"


_ENTRIES_POLICY = StringMappingPolicy(subject=_ENTRY_SUBJECT, value_whitespace=MappingValueWhitespace.STRIP)


_ENTRIES_FACT = StringMappingFact(fact_id=_FACT_ID, date_axis=DateAxis.FILING_PERIOD, policy=_ENTRIES_POLICY)


def _policy(entries: Mapping[str, str]) -> AmendmentRegimePolicy:
    procedure_order = unique_mapping_tokens(entries, _PROCEDURE_ORDER_KEY, subject=_ENTRY_SUBJECT)
    for token in procedure_order:
        if required_mapping_entry(entries, f"procedure.{token}.value", subject=_ENTRY_SUBJECT) != token:
            raise RegistryValidationError(
                f"amendment-regime-policy procedure {token!r} declares a mismatched value",
            )

    pre_order = unique_mapping_tokens(entries, _PRE_ORDER_KEY, subject=_ENTRY_SUBJECT)
    post_order = unique_mapping_tokens(entries, _POST_ORDER_KEY, subject=_ENTRY_SUBJECT)
    declared_procedures = frozenset(procedure_order)
    if not set(pre_order).issubset(declared_procedures):
        raise RegistryValidationError("amendment-regime-policy pre-regime uses an undeclared procedure")
    if not set(post_order).issubset(declared_procedures):
        raise RegistryValidationError("amendment-regime-policy post-regime uses an undeclared procedure")

    boundary_models = unique_mapping_tokens(entries, _BOUNDARY_ORDER_KEY, subject=_ENTRY_SUBJECT)
    boundaries: dict[str, date] = {}
    for modelo in boundary_models:
        try:
            boundaries[modelo] = date.fromisoformat(
                required_mapping_entry(entries, f"boundary.{modelo}.date", subject=_ENTRY_SUBJECT)
            )
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


def resolve_amendment_regime_policy(
    *,
    effective_date: date | None = None,
    authority: ValidatedRegistryAuthority | None = None,
) -> AmendmentRegimePolicy:
    """Resolve the selected dated amendment policy, failing closed if absent.

    Core types:
    :class:`~cadrumo.domain.calculations.registry.authority.ValidatedRegistryAuthority`.
    """
    return _policy(_ENTRIES_FACT.resolve_scoped_entries(effective_date=effective_date, authority=authority))


def resolve_amendment_regime_policy_for_period(
    period: Period,
    *,
    authority: ValidatedRegistryAuthority | None = None,
) -> AmendmentRegimePolicy:
    """Resolve amendment policy at the period's filing-period coordinate.

    Core types:
    :class:`~cadrumo.domain.calculations.registry.authority.ValidatedRegistryAuthority`.
    """
    effective_date = period.end_date if period.has_date_span() else date(period.filing_year, 12, 31)
    return resolve_amendment_regime_policy(effective_date=effective_date, authority=authority)


def resolve_amendment_kind_regime_for_period(
    modelo: str,
    period: Period,
    *,
    authority: ValidatedRegistryAuthority | None = None,
) -> AmendmentKindRegime:
    """Resolve a model/period amendment regime through the selected fact.

    Core types:
    :class:`~cadrumo.domain.calculations.registry.authority.ValidatedRegistryAuthority`.
    """
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
    """Return permitted amendment kinds from the registry-projected policy.

    Core types:
    :class:`~cadrumo.domain.calculations.registry.authority.ValidatedRegistryAuthority`.
    """
    return resolve_amendment_kind_regime_for_period(modelo, period, authority=authority).permitted_kinds


__all__ = [
    "permitted_amendment_kind_values_for_period",
    "resolve_amendment_kind_regime_for_period",
    "resolve_amendment_regime_policy",
    "resolve_amendment_regime_policy_for_period",
]
