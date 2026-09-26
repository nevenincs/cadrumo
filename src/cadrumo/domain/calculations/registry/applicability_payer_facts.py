"""Typed payer-fact predicates and projections for modelo applicability."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import date
from enum import StrEnum
from types import MappingProxyType, NoneType
from typing import TYPE_CHECKING, Final, get_args

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
    "PayerFactDeclaration",
    "PayerFactPeriodCompanion",
    "PayerFactProjection",
    "PayerFactValue",
    "payer_fact_declaration",
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


class PayerFactDeclaration(StrEnum):
    """What a profile says about one payer fact.

    ``UNDECLARED`` and ``PERIODS_UNDECLARED`` are both undeclared states: the
    second is a declared yes whose required period companion is absent or
    empty, kept distinct only so the rationale can name what is missing.
    """

    DECLARED_YES = "declared_yes"
    DECLARED_NO = "declared_no"
    UNDECLARED = "undeclared"
    PERIODS_UNDECLARED = "periods_undeclared"


@dataclass(frozen=True, slots=True)
class PayerFactPeriodCompanion:
    """The profile period set that must accompany a declared yes."""

    profile_key: str
    label: str


@dataclass(frozen=True, slots=True)
class PayerFactProjection:
    """One dated, registry-owned payer-applicability declaration.

    ``three_state`` is true when the profile field can hold an undeclared
    answer, so a stored ``False`` is a declared no. A plain boolean field keeps
    the two-state reading: ``False`` cannot be told apart from an unanswered
    question and stays undeclared.
    """

    token: str
    profile_key: str
    label: str
    legal_refs: tuple[str, ...]
    three_state: bool = False
    period_companion: PayerFactPeriodCompanion | None = None


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


def _profile_field_args(profile_key: str, *, token: str) -> frozenset[object]:
    field = TaxpayerProfile.model_fields.get(profile_key)
    if field is None:
        raise RegistryValidationError(
            f"payer applicability fact {token!r} names profile key {profile_key!r}, which the taxpayer profile "
            "does not declare",
        )
    annotation: object = field.annotation
    return frozenset(get_args(annotation) or (annotation,))


def _declaration_profile_key(profile_key: str, *, token: str) -> bool:
    """Validate a yes/no profile key and return whether it is three-state."""
    args = _profile_field_args(profile_key, token=token)
    if args == frozenset({bool}):
        return False
    if args == frozenset({bool, NoneType}):
        return True
    raise RegistryValidationError(
        f"payer applicability fact {token!r} profile key {profile_key!r} must be a boolean profile field",
    )


def _period_companion(
    entries: Mapping[str, str],
    prefix: str,
    *,
    token: str,
) -> PayerFactPeriodCompanion | None:
    if f"{prefix}period_set_key" not in entries:
        if f"{prefix}period_set_label" in entries:
            raise RegistryValidationError(f"payer applicability fact {token!r} labels an undeclared period set")
        return None
    profile_key = required_mapping_entry(entries, f"{prefix}period_set_key", subject=_ENTRY_SUBJECT)
    if _profile_field_args(profile_key, token=token) != frozenset({frozenset[str], NoneType}):
        raise RegistryValidationError(
            f"payer applicability fact {token!r} period set {profile_key!r} must be an optional token-set "
            "profile field",
        )
    return PayerFactPeriodCompanion(
        profile_key=profile_key,
        label=required_mapping_entry(entries, f"{prefix}period_set_label", subject=_ENTRY_SUBJECT),
    )


def _catalogue(entries: Mapping[str, str]) -> tuple[PayerFactProjection, ...]:
    definitions: list[PayerFactProjection] = []
    for raw_token in unique_mapping_tokens(entries, _ORDER_KEY, subject=_ENTRY_SUBJECT):
        prefix = f"{_PREFIX}{raw_token}."
        if required_mapping_entry(entries, f"{prefix}value", subject=_ENTRY_SUBJECT) != raw_token:
            raise RegistryValidationError(f"payer applicability fact {raw_token!r} declares a mismatched value")
        legal_refs = _pipe(entries, f"{prefix}legal_refs")
        profile_key = required_mapping_entry(entries, f"{prefix}profile_key", subject=_ENTRY_SUBJECT)
        definitions.append(
            PayerFactProjection(
                token=raw_token,
                profile_key=profile_key,
                label=required_mapping_entry(entries, f"{prefix}label", subject=_ENTRY_SUBJECT),
                legal_refs=legal_refs,
                three_state=_declaration_profile_key(profile_key, token=raw_token),
                period_companion=_period_companion(entries, prefix, token=raw_token),
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
    """Resolve the selected dated payer-applicability entity set.

    Core types:
    :class:`~cadrumo.domain.calculations.registry.authority.ValidatedRegistryAuthority`.
    """
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
    """Resolve a raw applicability token through mechanics or the dated fact.

    Core types:
    :class:`~cadrumo.domain.calculations.registry.authority.ValidatedRegistryAuthority`.
    """
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


def _projection_declaration(profile: TaxpayerProfile, fact: PayerFactProjection) -> PayerFactDeclaration:
    value = getattr(profile, fact.profile_key, None)
    if value is None and fact.three_state:
        return PayerFactDeclaration.UNDECLARED
    if not isinstance(value, bool):
        raise RegistryValidationError(
            f"payer applicability profile key {fact.profile_key!r} must resolve to a boolean",
        )
    if not value:
        return PayerFactDeclaration.DECLARED_NO if fact.three_state else PayerFactDeclaration.UNDECLARED
    if fact.period_companion is None:
        return PayerFactDeclaration.DECLARED_YES
    periods = getattr(profile, fact.period_companion.profile_key, None)
    if periods is not None and not isinstance(periods, frozenset):
        raise RegistryValidationError(
            f"payer applicability period set {fact.period_companion.profile_key!r} must resolve to a token set",
        )
    return PayerFactDeclaration.DECLARED_YES if periods else PayerFactDeclaration.PERIODS_UNDECLARED


def payer_fact_declaration(profile: TaxpayerProfile, fact: PayerFactValue) -> PayerFactDeclaration:
    """Return what ``profile`` declares about the supplied payer fact.

    A coded mechanics fact is two-state: its evaluator can prove a yes, and
    anything else stays undeclared.

    Core types:
    :class:`~cadrumo.domain.deadlines.models.TaxpayerProfile`.
    """
    if isinstance(fact, PayerFactProjection):
        return _projection_declaration(profile, fact)
    try:
        holds = _PAYER_FACT_EVALUATORS[fact](profile)
    except KeyError as exc:
        raise RegistryValidationError(f"payer applicability fact {fact!r} has no evaluator") from exc
    return PayerFactDeclaration.DECLARED_YES if holds else PayerFactDeclaration.UNDECLARED


def payer_fact_profile_keys(fact: PayerFactValue) -> tuple[str, ...]:
    """Return profile fields needed to answer an applicability fact."""
    if isinstance(fact, PayerFactProjection):
        if fact.period_companion is not None:
            return (fact.profile_key, fact.period_companion.profile_key)
        return (fact.profile_key,)
    return _PAYER_FACT_PROFILE_KEYS.get(fact, ())
