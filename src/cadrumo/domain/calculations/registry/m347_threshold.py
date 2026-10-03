"""The Modelo 347 per-counterparty declaration floor, in one place.

RD 1065/2007 art. 33.1 relates each person whose operations "en su conjunto"
exceed the floor during the año natural, and computes "de forma separada las
entregas y las adquisiciones de bienes y servicios". The floor is therefore
judged per counterparty AND per threshold bucket: the registry fact
``m347-clave-threshold-buckets`` says, per filing period, which claves de
operación are summed together and which scalar fact holds that bucket's floor
(or that the bucket is related whatever its amount). The summation of each
observation's amount stays with the caller; the bucket grouping and the
regulatory comparison live here.

Where the registry marks a bucket's grouping as an unsettled reading of the
law, the bucket says so (``reading_unsettled``) and the declarable set records
which unconditional buckets admitted a nil or negative total, so a caller can
surface both as advisories instead of presenting a contested reading as
settled.

This is a leaf module on purpose: the invoice binding family imports it, and
it imports nothing from any binding family, so no caller can grow a second
copy of the comparison to avoid a circular import.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Final

from .binding_selector_utils import M347_OPERATION_CLAVES
from .errors import RegistryValidationError
from .facts.resolution import ResolvedScalarFact, ScalarFactQuery, required_mapping_entry, unique_mapping_tokens
from .facts.string_mapping import (
    BooleanTokenCase,
    MappingValueWhitespace,
    StringMappingFact,
    StringMappingPolicy,
    required_mapping_boolean,
)
from .governed_fact_scope import GovernedFactSource, require_governed_fact_authority
from .schema_base import DateAxis

__all__ = [
    "M347DeclarableSet",
    "M347ThresholdBucket",
    "M347ThresholdBuckets",
    "m347_declarable_party_buckets",
    "m347_threshold_decimal",
    "resolve_m347_clave_c_declaration_threshold",
    "resolve_m347_counterparty_annual_threshold",
    "resolve_m347_threshold_buckets",
]


_M347_COUNTERPARTY_THRESHOLD_FACT_ID: Final = "m347-counterparty-declaration-threshold"
_M347_CLAVE_C_THRESHOLD_FACT_ID: Final = "m347-clave-c-beneficiary-declaration-threshold"
_M347_THRESHOLD_BUCKETS_SUBJECT: Final = "M347 clave threshold buckets"
_M347_THRESHOLD_BUCKETS_FACT: Final = StringMappingFact(
    fact_id="m347-clave-threshold-buckets",
    date_axis=DateAxis.FILING_PERIOD,
    policy=StringMappingPolicy(
        subject=_M347_THRESHOLD_BUCKETS_SUBJECT,
        value_whitespace=MappingValueWhitespace.STRIP,
    ),
)
_BUCKET_ORDER_KEY: Final = "bucket.order"
_BUCKET_PREFIX: Final = "bucket."
_BUCKET_FIELDS: Final = frozenset({"claves", "floor_fact", "declared_regardless_of_amount", "reading_unsettled"})


@dataclass(frozen=True, slots=True)
class M347ThresholdBucket:
    """One set of claves whose per-counterparty total is compared against one floor.

    ``floor`` is ``None`` only when the registry declares the bucket's
    operations related whatever their amount; a bucket with a floor always
    carries the resolved scalar fact that holds it. ``reading_unsettled`` is
    the registry's statement that this grouping, or its floor, follows one
    reading of a text the corpus does not settle for the filing period.
    """

    token: str
    claves: frozenset[str]
    floor: Decimal | None
    floor_fact: ResolvedScalarFact | None
    reading_unsettled: bool = False


@dataclass(frozen=True, slots=True)
class M347ThresholdBuckets:
    """The selected filing period's partition of every M347 clave into buckets."""

    buckets: tuple[M347ThresholdBucket, ...]
    effective_date: date

    def bucket_of(self, clave: str) -> M347ThresholdBucket:
        """Return the bucket ``clave`` is summed in; refuse a clave no bucket names."""
        for bucket in self.buckets:
            if clave in bucket.claves:
                return bucket
        raise RegistryValidationError(
            f"{_M347_THRESHOLD_BUCKETS_SUBJECT} for {self.effective_date.isoformat()} "
            f"assign no bucket to clave {clave!r}",
        )


@dataclass(frozen=True, slots=True)
class M347DeclarableSet:
    """The (counterparty, bucket) pairs whose summed total must be declared.

    ``unconditional_nonpositive`` holds the declarable pairs admitted by a
    bucket with no floor whose summed total is zero or negative: the bucket
    relates them whatever their amount, but a nil or negative annual total is
    the case the declaration's own sign field exists for and is not settled by
    the floor rule.
    """

    buckets: M347ThresholdBuckets
    declarable: frozenset[tuple[str, str]]
    unconditional_nonpositive: frozenset[tuple[str, str]] = frozenset()

    def admits(self, party_tax_id: str, clave: str) -> bool:
        """Whether an operation with ``party_tax_id`` under ``clave`` is declared."""
        return (party_tax_id, self.buckets.bucket_of(clave).token) in self.declarable

    def admits_unconditional_nonpositive(self, party_tax_id: str, clave: str) -> bool:
        """Whether that operation is declared by a no-floor bucket on a zero or negative total."""
        return (party_tax_id, self.buckets.bucket_of(clave).token) in self.unconditional_nonpositive


def _resolve_m347_floor_fact(
    fact_id: str,
    *,
    effective_date: date,
    authority: GovernedFactSource,
) -> ResolvedScalarFact:
    resolved = authority.resolve_governed_fact(
        ScalarFactQuery(
            fact_id=fact_id,
            date_axis=DateAxis.FILING_PERIOD,
            effective_date=effective_date,
        ),
    )
    if not isinstance(resolved, ResolvedScalarFact):
        raise RegistryValidationError(f"M347 floor fact {fact_id!r} must resolve as a scalar fact")
    return resolved


def resolve_m347_counterparty_annual_threshold(
    *,
    effective_date: date,
    authority: GovernedFactSource | None = None,
) -> ResolvedScalarFact:
    """Resolve the canonical annual counterparty threshold with provenance."""
    selected = require_governed_fact_authority(authority, subject="M347 counterparty threshold")
    return _resolve_m347_floor_fact(
        _M347_COUNTERPARTY_THRESHOLD_FACT_ID,
        effective_date=effective_date,
        authority=selected,
    )


def resolve_m347_clave_c_declaration_threshold(
    *,
    effective_date: date,
    authority: GovernedFactSource | None = None,
) -> ResolvedScalarFact:
    """Resolve the distinct clave-C threshold with its statutory provenance."""
    selected = require_governed_fact_authority(authority, subject="M347 clave-C threshold")
    return _resolve_m347_floor_fact(
        _M347_CLAVE_C_THRESHOLD_FACT_ID,
        effective_date=effective_date,
        authority=selected,
    )


def m347_threshold_decimal(threshold: ResolvedScalarFact) -> Decimal:
    """Return a resolved M347 monetary threshold only when it is a Decimal."""
    value = threshold.payload.value
    if not isinstance(value, Decimal):
        raise RegistryValidationError(
            f"M347 threshold fact {threshold.fact_id!r} resolved non-decimal payload {value!r}",
        )
    return value


def resolve_m347_threshold_buckets(
    *,
    effective_date: date,
    authority: GovernedFactSource | None = None,
) -> M347ThresholdBuckets:
    """Resolve the filing period's clave buckets and each bucket's floor.

    The fact must partition the whole M347 clave vocabulary: every clave in
    exactly one bucket, and every bucket naming either one floor fact or an
    explicit ``declared_regardless_of_amount = true``, never both and never
    neither. A bucket may add ``reading_unsettled = true``; absent, the
    grouping is settled.

    Raises:
        RegistryValidationError: When the fact is malformed, leaves a clave
            unassigned or assigns one twice, or names a floor fact that does
            not resolve as a decimal scalar.
    """
    selected = require_governed_fact_authority(authority, subject=_M347_THRESHOLD_BUCKETS_SUBJECT)
    entries = _M347_THRESHOLD_BUCKETS_FACT.resolve_entries(selected, effective_date=effective_date)
    tokens = unique_mapping_tokens(entries, _BUCKET_ORDER_KEY, subject=_M347_THRESHOLD_BUCKETS_SUBJECT)
    _refuse_undeclared_bucket_entries(entries, frozenset(tokens))
    buckets = tuple(_bucket(entries, token, effective_date=effective_date, authority=selected) for token in tokens)
    assigned = [clave for bucket in buckets for clave in bucket.claves]
    if len(assigned) != len(set(assigned)) or set(assigned) != M347_OPERATION_CLAVES:
        raise RegistryValidationError(
            f"{_M347_THRESHOLD_BUCKETS_SUBJECT} must assign every clave in "
            f"{sorted(M347_OPERATION_CLAVES)} to exactly one bucket, got {sorted(assigned)}",
        )
    return M347ThresholdBuckets(buckets=buckets, effective_date=effective_date)


def _refuse_undeclared_bucket_entries(entries: Mapping[str, str], tokens: frozenset[str]) -> None:
    for key in entries:
        if key == _BUCKET_ORDER_KEY:
            continue
        token, _, field = key.removeprefix(_BUCKET_PREFIX).rpartition(".")
        if not key.startswith(_BUCKET_PREFIX) or token not in tokens or field not in _BUCKET_FIELDS:
            raise RegistryValidationError(f"{_M347_THRESHOLD_BUCKETS_SUBJECT} declares unknown entry {key!r}")


def _bucket(
    entries: Mapping[str, str],
    token: str,
    *,
    effective_date: date,
    authority: GovernedFactSource,
) -> M347ThresholdBucket:
    prefix = f"{_BUCKET_PREFIX}{token}."
    claves = frozenset(unique_mapping_tokens(entries, f"{prefix}claves", subject=_M347_THRESHOLD_BUCKETS_SUBJECT))
    unknown = claves - M347_OPERATION_CLAVES
    if unknown:
        raise RegistryValidationError(
            f"{_M347_THRESHOLD_BUCKETS_SUBJECT} bucket {token!r} names unknown claves {sorted(unknown)}",
        )
    has_floor = f"{prefix}floor_fact" in entries
    regardless_key = f"{prefix}declared_regardless_of_amount"
    regardless = regardless_key in entries and required_mapping_boolean(
        entries,
        regardless_key,
        subject=_M347_THRESHOLD_BUCKETS_SUBJECT,
        case=BooleanTokenCase.EXACT,
    )
    if has_floor == regardless or (regardless_key in entries and not regardless):
        raise RegistryValidationError(
            f"{_M347_THRESHOLD_BUCKETS_SUBJECT} bucket {token!r} must declare exactly one of a floor_fact "
            "or declared_regardless_of_amount = true",
        )
    unsettled_key = f"{prefix}reading_unsettled"
    reading_unsettled = unsettled_key in entries and required_mapping_boolean(
        entries,
        unsettled_key,
        subject=_M347_THRESHOLD_BUCKETS_SUBJECT,
        case=BooleanTokenCase.EXACT,
    )
    if regardless:
        return M347ThresholdBucket(
            token=token,
            claves=claves,
            floor=None,
            floor_fact=None,
            reading_unsettled=reading_unsettled,
        )
    floor_fact = _resolve_m347_floor_fact(
        required_mapping_entry(entries, f"{prefix}floor_fact", subject=_M347_THRESHOLD_BUCKETS_SUBJECT),
        effective_date=effective_date,
        authority=authority,
    )
    return M347ThresholdBucket(
        token=token,
        claves=claves,
        floor=m347_threshold_decimal(floor_fact),
        floor_fact=floor_fact,
        reading_unsettled=reading_unsettled,
    )


def _declarable_party_ids(totals: Mapping[str, Decimal], *, floor: Decimal) -> frozenset[str]:
    """The one comparison every M347 declaration-floor caller shares.

    The floor is *exceeded*, never merely reached: a party landing exactly
    on the figure is not declarable (RD 1065/2007 art. 33.1 "hayan superado
    la cifra"). The operator is therefore ``>``, and a ``>=`` here would
    over-declare every party sitting on the threshold -- which is the
    mutation this function's single home exists to make visible.
    """
    return frozenset(party_tax_id for party_tax_id, total in totals.items() if total > floor)


def m347_declarable_party_buckets(
    clave_totals: Mapping[tuple[str, str], Decimal],
    *,
    effective_date: date,
    authority: GovernedFactSource | None = None,
) -> M347DeclarableSet:
    """Return the (counterparty, bucket) pairs that pass their bucket's floor.

    Args:
        clave_totals: Summed Modelo 347 amount per ``(party_tax_id, clave)``.
            The amounts of the claves one bucket groups are added together
            per party (entregas B+F, adquisiciones A+G under the current
            fact), and each bucket is judged against its own floor: RD
            1065/2007 art. 33.1 computes entregas and adquisiciones
            separately, and arts. 32.c and 33.4 give clave C its own lower
            floor. A bucket the registry declares related whatever its
            amount admits every party that has an operation in it, and
            records the admitted parties whose total is zero or negative.
        effective_date: Explicit filing-period date selecting the governed facts.
        authority: Optional validated authority whose resolution retains provenance.

    Returns:
        The declarable set; :meth:`M347DeclarableSet.admits` answers per
        operation.
    """
    buckets = resolve_m347_threshold_buckets(effective_date=effective_date, authority=authority)
    bucket_totals: dict[str, dict[str, Decimal]] = {bucket.token: {} for bucket in buckets.buckets}
    for (party_tax_id, clave), amount in clave_totals.items():
        totals = bucket_totals[buckets.bucket_of(clave).token]
        totals[party_tax_id] = totals.get(party_tax_id, Decimal("0")) + amount
    declarable: set[tuple[str, str]] = set()
    unconditional_nonpositive: set[tuple[str, str]] = set()
    for bucket in buckets.buckets:
        totals = bucket_totals[bucket.token]
        if bucket.floor is None:
            parties = frozenset(totals)
            unconditional_nonpositive.update(
                (party_tax_id, bucket.token) for party_tax_id, total in totals.items() if total <= 0
            )
        else:
            parties = _declarable_party_ids(totals, floor=bucket.floor)
        declarable.update((party_tax_id, bucket.token) for party_tax_id in parties)
    return M347DeclarableSet(
        buckets=buckets,
        declarable=frozenset(declarable),
        unconditional_nonpositive=frozenset(unconditional_nonpositive),
    )
