"""Typed payer-fact predicates and projections for modelo applicability."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import date
from enum import StrEnum
from types import MappingProxyType
from typing import TYPE_CHECKING, Final

from ....core.time.clock import today_madrid
from ...deadlines.models import TaxpayerProfile
from .errors import RegistryValidationError
from .facts.resolution import MappingFactQuery, ResolvedMappingFact, required_mapping_entry, unique_mapping_tokens
from .governed_fact_scope import GovernedFactSource, cache_governed_projection, governed_facts_in_scope
from .schema_base import DateAxis

_ENTRY_SUBJECT: Final = "payer applicability fact"

if TYPE_CHECKING:
    from .authority import ValidatedRegistryAuthority

__all__ = [
    "PayerFact",
    "PayerFactProjection",
    "PayerFactValue",
    "payer_fact_holds",
    "payer_fact_profile_keys",
    "resolve_payer_fact",
    "resolve_payer_fact_catalogue",
]


class PayerFact(StrEnum):
    """Application-mechanics payer facts not owned by the dated catalogue."""

    PAYS_WITHHELD_INCOME = "pays_withheld_income"
    PAYS_RENT_WITH_RETENCION = "pays_rent_with_retencion"
    TRADES_INTRACOMMUNITY = "trades_intracommunity"
    IVA_GROUP_MEMBER = "iva_group_member"
    IVA_GROUP_DOMINANT_ENTITY = "iva_group_dominant_entity"
    OSS_ENROLLED = "oss_enrolled"


@dataclass(frozen=True, slots=True)
class PayerFactProjection:
    """One dated, registry-owned payer-applicability declaration."""

    token: str
    profile_key: str
    label: str
    legal_refs: tuple[str, ...]


type PayerFactValue = PayerFact | PayerFactProjection
type _PayerFactEvaluator = Callable[[TaxpayerProfile], bool]


_FACT_ID = "modelo-payer-applicability-facts"
_ORDER_KEY = "payer_fact.order"
_PREFIX = "payer_fact."


_PAYER_FACT_EVALUATORS: Mapping[PayerFact, _PayerFactEvaluator] = MappingProxyType(
    {
        PayerFact.PAYS_WITHHELD_INCOME: (
            lambda profile: profile.has_employees or profile.pays_professionals_with_retencion
        ),
        PayerFact.PAYS_RENT_WITH_RETENCION: lambda profile: profile.pays_rent_with_retencion,
        PayerFact.TRADES_INTRACOMMUNITY: lambda profile: profile.does_intracomunitario,
        PayerFact.IVA_GROUP_MEMBER: (lambda profile: profile.iva is not None and profile.iva.group_member_enrolled),
        PayerFact.IVA_GROUP_DOMINANT_ENTITY: (
            lambda profile: profile.iva is not None and profile.iva.group_dominant_entity_enrolled
        ),
        PayerFact.OSS_ENROLLED: lambda profile: profile.iva is not None and profile.iva.oss_enrolled,
    },
)


_PAYER_FACT_PROFILE_KEYS: Mapping[PayerFact, tuple[str, ...]] = MappingProxyType(
    {
        PayerFact.PAYS_WITHHELD_INCOME: ("has_employees", "pays_professionals_with_retencion"),
        PayerFact.PAYS_RENT_WITH_RETENCION: ("pays_rent_with_retencion",),
        PayerFact.TRADES_INTRACOMMUNITY: ("does_intracomunitario",),
        PayerFact.IVA_GROUP_MEMBER: ("iva",),
        PayerFact.IVA_GROUP_DOMINANT_ENTITY: ("iva",),
        PayerFact.OSS_ENROLLED: ("iva",),
    },
)


def _mapping_entries(resolved: ResolvedMappingFact) -> Mapping[str, str]:
    entries: dict[str, str] = {}
    for entry in resolved.payload.entries:
        if not isinstance(entry.key, str) or not isinstance(entry.value, str):
            raise RegistryValidationError("payer applicability fact entries must be string-to-string")
        if entry.key in entries:
            raise RegistryValidationError(f"duplicate payer applicability fact key {entry.key!r}")
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
        raise RegistryValidationError(f"payer applicability fact {_FACT_ID!r} must resolve as a mapping")
    return _mapping_entries(resolved)


@cache_governed_projection(maxsize=64)
def _bundled_mapping_entries(effective_date: date) -> Mapping[str, str]:
    del effective_date
    raise RegistryValidationError("payer-fact catalogue requires an explicit authority operation or scope")


def _selected_mapping_entries(
    *,
    effective_date: date,
    authority: ValidatedRegistryAuthority | None,
) -> Mapping[str, str]:
    selected = authority or governed_facts_in_scope()
    if selected is None:
        return _bundled_mapping_entries(effective_date)
    return _resolve_entries(effective_date=effective_date, authority=selected)


def _pipe(entries: Mapping[str, str], key: str) -> tuple[str, ...]:
    values = tuple(
        token.strip()
        for token in required_mapping_entry(entries, key, subject=_ENTRY_SUBJECT).split("|")
        if token.strip()
    )
    if not values or len(values) != len(set(values)):
        raise RegistryValidationError(f"payer applicability fact {key!r} must contain unique references")
    return values


def _catalogue(entries: Mapping[str, str]) -> tuple[PayerFactProjection, ...]:
    definitions: list[PayerFactProjection] = []
    for raw_token in unique_mapping_tokens(entries, _ORDER_KEY, subject=_ENTRY_SUBJECT):
        prefix = f"{_PREFIX}{raw_token}."
        if required_mapping_entry(entries, f"{prefix}value", subject=_ENTRY_SUBJECT) != raw_token:
            raise RegistryValidationError(f"payer applicability fact {raw_token!r} declares a mismatched value")
        legal_refs = _pipe(entries, f"{prefix}legal_refs")
        definitions.append(
            PayerFactProjection(
                token=raw_token,
                profile_key=required_mapping_entry(entries, f"{prefix}profile_key", subject=_ENTRY_SUBJECT),
                label=required_mapping_entry(entries, f"{prefix}label", subject=_ENTRY_SUBJECT),
                legal_refs=legal_refs,
            ),
        )
    if len({item.token for item in definitions}) != len(definitions):
        raise RegistryValidationError("payer applicability fact contains duplicate declarations")
    return tuple(definitions)


@cache_governed_projection(maxsize=64)
def _bundled_catalogue(effective_date: date) -> tuple[PayerFactProjection, ...]:
    return _catalogue(_bundled_mapping_entries(effective_date))


def resolve_payer_fact_catalogue(
    *,
    effective_date: date | None = None,
    authority: ValidatedRegistryAuthority | None = None,
) -> tuple[PayerFactProjection, ...]:
    """Resolve the selected dated payer-applicability entity set."""
    coordinate = effective_date or today_madrid()
    if authority is None and governed_facts_in_scope() is None:
        return _bundled_catalogue(coordinate)
    return _catalogue(_selected_mapping_entries(effective_date=coordinate, authority=authority))


def resolve_payer_fact(
    value: str | PayerFact | PayerFactProjection,
    *,
    effective_date: date | None = None,
    authority: ValidatedRegistryAuthority | None = None,
) -> PayerFactValue:
    """Resolve a raw applicability token through mechanics or the dated fact."""
    if isinstance(value, PayerFactProjection):
        return value
    if isinstance(value, PayerFact):
        return value
    if not isinstance(value, str) or not value.strip():
        raise RegistryValidationError("payer applicability fact must be a non-empty string token")
    raw = value.strip()
    try:
        return PayerFact(raw)
    except ValueError:
        for projection in resolve_payer_fact_catalogue(effective_date=effective_date, authority=authority):
            if projection.token == raw:
                return projection
    raise RegistryValidationError(f"payer applicability fact {raw!r} is not declared by the selected registry")


def payer_fact_holds(profile: TaxpayerProfile, fact: PayerFactValue) -> bool:
    """Return whether ``profile`` positively declares the supplied payer fact."""
    if isinstance(fact, PayerFactProjection):
        value = getattr(profile, fact.profile_key, None)
        if not isinstance(value, bool):
            raise RegistryValidationError(
                f"payer applicability profile key {fact.profile_key!r} must resolve to a boolean",
            )
        return value
    try:
        return _PAYER_FACT_EVALUATORS[fact](profile)
    except KeyError as exc:
        raise RegistryValidationError(f"payer applicability fact {fact!r} has no evaluator") from exc


def payer_fact_profile_keys(fact: PayerFactValue) -> tuple[str, ...]:
    """Return profile fields needed to answer an applicability fact."""
    if isinstance(fact, PayerFactProjection):
        return (fact.profile_key,)
    return _PAYER_FACT_PROFILE_KEYS.get(fact, ())
