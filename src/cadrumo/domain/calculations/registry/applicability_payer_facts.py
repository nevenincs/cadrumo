"""Typed payer-fact predicates and projections for modelo applicability."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import date
from enum import StrEnum
from types import MappingProxyType, NoneType
from typing import TYPE_CHECKING, Final, get_args

from pydantic import BaseModel

from ....core.errors.hierarchy import CoreValidationError
from ....core.modelo import Modelo
from ....core.period import is_filing_period_token
from ...deadlines.models import TaxpayerProfile
from .errors import RegistryValidationError
from .facts.resolution import UNIQUE_REFERENCES_REQUIREMENT, required_mapping_entry, unique_mapping_tokens
from .facts.string_mapping import (
    MappingValueWhitespace,
    StringMappingFact,
    StringMappingPolicy,
)
from .schema_base import DateAxis

_ENTRY_SUBJECT: Final = "payer applicability fact"

if TYPE_CHECKING:
    from .authority import ValidatedRegistryAuthority

__all__ = [
    "PayerFact",
    "PayerFactDeclaration",
    "PayerFactLedgerSource",
    "PayerFactPeriodCompanion",
    "PayerFactProjection",
    "PayerFactValue",
    "payer_fact_declaration",
    "payer_fact_profile_keys",
    "profile_path_value",
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
class PayerFactLedgerSource:
    """The filing whose own declared-record count answers a payer fact from the taxpayer's ledger.

    The fact holds for a filing year exactly when that modelo's filing for the
    year would declare at least one record: ``record_count_binding`` is the
    binding counting those records on the modelo's revision for ``period``.
    """

    modelo: Modelo
    period: str
    record_count_binding: str


@dataclass(frozen=True, slots=True)
class PayerFactProjection:
    """One dated, registry-owned payer-applicability declaration.

    ``profile_keys`` names the profile fields the fact reads, as dotted paths
    from the taxpayer profile. A single key is the fact itself; several keys
    form a derived fact that holds when any of them is declared yes.

    ``three_state`` is true when a field can hold an undeclared answer, either
    because it is optional or because it sits in an optional profile section,
    so a stored ``False`` everywhere is a declared no. A plain boolean field
    keeps the two-state reading: ``False`` cannot be told apart from an
    unanswered question and stays undeclared.

    ``ledger_source`` is set when the registry declares that the taxpayer's own
    records can answer the fact, through a :class:`PayerFactLedgerSource`.
    """

    token: str
    profile_keys: tuple[str, ...]
    label: str
    legal_refs: tuple[str, ...]
    three_state: bool = False
    period_companion: PayerFactPeriodCompanion | None = None
    ledger_source: PayerFactLedgerSource | None = None


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


_ENTRIES_POLICY = StringMappingPolicy(subject=_ENTRY_SUBJECT, value_whitespace=MappingValueWhitespace.STRIP)


_ENTRIES_FACT = StringMappingFact(fact_id=_FACT_ID, date_axis=DateAxis.FILING_PERIOD, policy=_ENTRIES_POLICY)


def _profile_path_args(profile_key: str, *, token: str) -> tuple[frozenset[object], bool]:
    """Return a dotted profile path's leaf annotation and whether it crosses an optional section."""
    model: type[BaseModel] = TaxpayerProfile
    in_optional_section = False
    segments = profile_key.split(".")
    for index, segment in enumerate(segments):
        field = model.model_fields.get(segment)
        if field is None:
            raise RegistryValidationError(
                f"payer applicability fact {token!r} names profile key {profile_key!r}, which the taxpayer profile "
                "does not declare",
            )
        annotation: object = field.annotation
        args = frozenset(get_args(annotation) or (annotation,))
        if index == len(segments) - 1:
            return args, in_optional_section
        model, optional_section = _profile_section_model(args, profile_key=profile_key, segment=segment, token=token)
        in_optional_section = in_optional_section or optional_section
    raise RegistryValidationError(f"payer applicability fact {token!r} names an empty profile key")


def _profile_section_model(
    args: frozenset[object],
    *,
    profile_key: str,
    segment: str,
    token: str,
) -> tuple[type[BaseModel], bool]:
    """Resolve one non-leaf path segment as a declared profile section."""
    section_models = [arg for arg in args if isinstance(arg, type) and issubclass(arg, BaseModel)]
    if len(section_models) != 1 or not args <= {section_models[0], NoneType}:
        raise RegistryValidationError(
            f"payer applicability fact {token!r} profile key {profile_key!r} crosses {segment!r}, which is not "
            "a profile section",
        )
    return section_models[0], NoneType in args


def _profile_field_args(profile_key: str, *, token: str) -> frozenset[object]:
    return _profile_path_args(profile_key, token=token)[0]


def _declaration_profile_key(profile_key: str, *, token: str) -> bool:
    """Validate a yes/no profile key and return whether it is three-state."""
    args, in_optional_section = _profile_path_args(profile_key, token=token)
    if args == frozenset({bool}):
        return in_optional_section
    if args == frozenset({bool, NoneType}):
        return True
    raise RegistryValidationError(
        f"payer applicability fact {token!r} profile key {profile_key!r} must be a boolean profile field",
    )


def _declaration_profile_keys(entries: Mapping[str, str], prefix: str, *, token: str) -> tuple[str, ...]:
    """Return the single key, or the keys of a derived any-of fact."""
    single = f"{prefix}profile_key"
    any_of = f"{prefix}any_of_profile_keys"
    if (single in entries) == (any_of in entries):
        raise RegistryValidationError(
            f"payer applicability fact {token!r} must declare exactly one of profile_key or any_of_profile_keys",
        )
    if single in entries:
        return (required_mapping_entry(entries, single, subject=_ENTRY_SUBJECT),)
    keys = unique_mapping_tokens(
        entries, any_of, subject=_ENTRY_SUBJECT, requirement=UNIQUE_REFERENCES_REQUIREMENT, separator="|"
    )
    if len(keys) < 2:
        raise RegistryValidationError(f"payer applicability fact {token!r} derives from fewer than two profile keys")
    if f"{prefix}period_set_key" in entries:
        raise RegistryValidationError(f"payer applicability fact {token!r} derives from several keys and a period set")
    return keys


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


_LEDGER_SOURCE_FIELDS: Final = ("ledger_modelo", "ledger_period", "ledger_record_count_binding")


def _ledger_source(
    entries: Mapping[str, str],
    prefix: str,
    *,
    token: str,
    period_companion: PayerFactPeriodCompanion | None,
) -> PayerFactLedgerSource | None:
    """Hydrate the declared ledger source: all three fields or none."""
    present = [field for field in _LEDGER_SOURCE_FIELDS if f"{prefix}{field}" in entries]
    if not present:
        return None
    if len(present) != len(_LEDGER_SOURCE_FIELDS):
        raise RegistryValidationError(
            f"payer applicability fact {token!r} declares an incomplete ledger source: it needs "
            f"{', '.join(_LEDGER_SOURCE_FIELDS)}",
        )
    if period_companion is not None:
        raise RegistryValidationError(
            f"payer applicability fact {token!r} derives from the ledger and a period set; a ledger derivation "
            "states no periods",
        )
    raw_modelo, period, binding = (
        required_mapping_entry(entries, f"{prefix}{field}", subject=_ENTRY_SUBJECT) for field in _LEDGER_SOURCE_FIELDS
    )
    try:
        modelo = Modelo(raw_modelo)
    except CoreValidationError as exc:
        raise RegistryValidationError(
            f"payer applicability fact {token!r} ledger source names an invalid modelo {raw_modelo!r}",
        ) from exc
    if not is_filing_period_token(period):
        raise RegistryValidationError(
            f"payer applicability fact {token!r} ledger source names {period!r}, which is not a filing period",
        )
    return PayerFactLedgerSource(modelo=modelo, period=period, record_count_binding=binding)


def _catalogue(entries: Mapping[str, str]) -> tuple[PayerFactProjection, ...]:
    definitions: list[PayerFactProjection] = []
    for raw_token in unique_mapping_tokens(entries, _ORDER_KEY, subject=_ENTRY_SUBJECT):
        prefix = f"{_PREFIX}{raw_token}."
        if required_mapping_entry(entries, f"{prefix}value", subject=_ENTRY_SUBJECT) != raw_token:
            raise RegistryValidationError(f"payer applicability fact {raw_token!r} declares a mismatched value")
        legal_refs = unique_mapping_tokens(
            entries,
            f"{prefix}legal_refs",
            subject=_ENTRY_SUBJECT,
            requirement=UNIQUE_REFERENCES_REQUIREMENT,
            separator="|",
        )
        profile_keys = _declaration_profile_keys(entries, prefix, token=raw_token)
        # Every key is validated; a short-circuiting any() would leave later keys unchecked.
        key_three_states = [_declaration_profile_key(key, token=raw_token) for key in profile_keys]
        period_companion = _period_companion(entries, prefix, token=raw_token)
        definitions.append(
            PayerFactProjection(
                token=raw_token,
                profile_keys=profile_keys,
                label=required_mapping_entry(entries, f"{prefix}label", subject=_ENTRY_SUBJECT),
                legal_refs=legal_refs,
                three_state=any(key_three_states),
                period_companion=period_companion,
                ledger_source=_ledger_source(entries, prefix, token=raw_token, period_companion=period_companion),
            ),
        )
    if len({item.token for item in definitions}) != len(definitions):
        raise RegistryValidationError("payer applicability fact contains duplicate declarations")
    return tuple(definitions)


def resolve_payer_fact_catalogue(
    *,
    effective_date: date | None = None,
    authority: ValidatedRegistryAuthority | None = None,
) -> tuple[PayerFactProjection, ...]:
    """Resolve the selected dated payer-applicability entity set.

    Core types:
    :class:`~cadrumo.domain.calculations.registry.authority.ValidatedRegistryAuthority`.
    """
    return _catalogue(_ENTRIES_FACT.resolve_scoped_entries(effective_date=effective_date, authority=authority))


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


def profile_path_value(profile: TaxpayerProfile, profile_key: str) -> object:
    """Read a dotted profile path; an absent optional section reads as unanswered."""
    current: object = profile
    for segment in profile_key.split("."):
        if current is None:
            return None
        current = getattr(current, segment, None)
    return current


def _validated_projection_values(profile: TaxpayerProfile, fact: PayerFactProjection) -> tuple[object, ...]:
    """Read every projected profile value, then validate them in authored order."""
    values = tuple(profile_path_value(profile, key) for key in fact.profile_keys)
    for key, value in zip(fact.profile_keys, values, strict=True):
        if not (isinstance(value, bool) or (value is None and fact.three_state)):
            raise RegistryValidationError(
                f"payer applicability profile key {key!r} must resolve to a boolean",
            )
    return values


def _projection_yes_declaration(profile: TaxpayerProfile, fact: PayerFactProjection) -> PayerFactDeclaration:
    """Resolve a declared yes and its optional period companion."""
    if fact.period_companion is None:
        return PayerFactDeclaration.DECLARED_YES
    periods = getattr(profile, fact.period_companion.profile_key, None)
    if periods is not None and not isinstance(periods, frozenset):
        raise RegistryValidationError(
            f"payer applicability period set {fact.period_companion.profile_key!r} must resolve to a token set",
        )
    return PayerFactDeclaration.DECLARED_YES if periods else PayerFactDeclaration.PERIODS_UNDECLARED


def _projection_declaration(profile: TaxpayerProfile, fact: PayerFactProjection) -> PayerFactDeclaration:
    values = _validated_projection_values(profile, fact)
    if not any(value is True for value in values):
        if any(value is None for value in values):
            return PayerFactDeclaration.UNDECLARED
        return PayerFactDeclaration.DECLARED_NO if fact.three_state else PayerFactDeclaration.UNDECLARED
    return _projection_yes_declaration(profile, fact)


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
            return (*fact.profile_keys, fact.period_companion.profile_key)
        return fact.profile_keys
    return _PAYER_FACT_PROFILE_KEYS.get(fact, ())
