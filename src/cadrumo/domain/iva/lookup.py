"""Lookup helpers for IVA registry data.

:func:`lookup_rate` resolves :class:`EUMemberState` and :class:`IvaRateKind`
queries into :class:`IvaRateRecord` records projected from governed-fact
authority results; :func:`rate_table_covers`
answers whether the table reaches a date at all; :func:`cite` renders
:class:`IvaCategory` catalogue citations from an :class:`IvaCatalogue`.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import TYPE_CHECKING, cast

from ..calculations.registry.facts.resolution import MappingFactQuery, ResolvedMappingFact
from ..calculations.registry.facts.schema import FactSelector
from ..calculations.registry.schema_base import DateAxis
from .errors import IvaRateNotFoundError
from .rates import IVA_RATE_FACT_ID, iva_rate_record_from_fact
from .schema import EUMemberState, IvaRateKind, IvaRateRecord

if TYPE_CHECKING:
    from ..calculations.registry.authority import ValidatedRegistryAuthority


def _authority(authority: ValidatedRegistryAuthority | None) -> ValidatedRegistryAuthority:
    """Return the bundled validated authority without importing it through the module graph."""
    if authority is None:
        from ..calculations.registry.authority import bundled_authority

        authority = bundled_authority()
    return authority


def resolve_iva_rate(
    member_state: EUMemberState,
    kind: IvaRateKind,
    on_date: date,
    *,
    rate_role: str = "ordinary",
    authority: ValidatedRegistryAuthority | None = None,
) -> ResolvedMappingFact:
    """Resolve one dated IVA rate fact and retain the complete authority provenance."""
    resolved = _authority(authority).resolve_governed_fact(
        MappingFactQuery(
            fact_id=IVA_RATE_FACT_ID,
            date_axis=DateAxis.DEVENGO_DATE,
            effective_date=on_date,
            selectors=(
                FactSelector(name="member_state", value=member_state.value),
                FactSelector(name="kind", value=kind.value),
                FactSelector(name="rate_role", value=rate_role),
            ),
        ),
    )
    return cast("ResolvedMappingFact", resolved)


def _member_state_is_registered(
    member_state: EUMemberState,
    *,
    authority: ValidatedRegistryAuthority | None = None,
) -> bool:
    """Return whether the rate fact declares any variant for ``member_state``."""
    resolved_authority = _authority(authority)
    resolved_authority.validate_registry()
    fact = resolved_authority.catalogues.facts.facts.get(IVA_RATE_FACT_ID)
    if fact is None:
        return False
    return any(
        {selector.name: selector.value for selector in variant.selectors}.get("member_state") == member_state.value
        for variant in fact.variants
    )


def _iva_rate_candidate_exists(
    member_state: EUMemberState,
    kind: IvaRateKind,
    on_date: date,
    *,
    rate_role: str = "ordinary",
    authority: ValidatedRegistryAuthority | None = None,
) -> bool:
    """Separate a genuine absence from an ambiguous authority resolution."""
    resolved_authority = _authority(authority)
    resolved_authority.validate_registry()
    fact = resolved_authority.catalogues.facts.facts.get(IVA_RATE_FACT_ID)
    if fact is None:
        return False
    expected = {
        "member_state": member_state.value,
        "kind": kind.value,
        "rate_role": rate_role,
    }
    return any(
        variant.date_axis is DateAxis.DEVENGO_DATE
        and variant.valid_from <= on_date
        and (variant.valid_to is None or on_date <= variant.valid_to)
        and {selector.name: selector.value for selector in variant.selectors} == expected
        for variant in fact.variants
    )


def _in_force_rate_facts(
    member_state: EUMemberState,
    on_date: date,
    *,
    authority: ValidatedRegistryAuthority | None = None,
) -> tuple[ResolvedMappingFact, ...]:
    """Resolve every IVA fact variant in force for a member state at one devengo date."""
    resolved_authority = _authority(authority)
    resolved_authority.validate_registry()
    fact = resolved_authority.catalogues.facts.facts.get(IVA_RATE_FACT_ID)
    if fact is None:
        return ()
    candidates = tuple(
        variant
        for variant in fact.variants
        if variant.date_axis is DateAxis.DEVENGO_DATE
        and variant.valid_from <= on_date
        and (variant.valid_to is None or on_date <= variant.valid_to)
        and {selector.name: selector.value for selector in variant.selectors}.get("member_state") == member_state.value
    )
    return tuple(
        resolve_iva_rate(
            member_state,
            IvaRateKind(str({selector.name: selector.value for selector in variant.selectors}["kind"])),
            on_date,
            rate_role=str({selector.name: selector.value for selector in variant.selectors}["rate_role"]),
            authority=resolved_authority,
        )
        for variant in candidates
    )


def lookup_rate(
    member_state: EUMemberState,
    kind: IvaRateKind,
    on_date: date,
) -> IvaRateRecord:
    """Return the :class:`cadrumo.domain.iva.IvaRateRecord` matching the supplied query.

    Resolves the ordinary governed-fact variant for the exact member-state,
    tier, and devengo-date coordinates, then projects it onto the established
    public record.

    Args:
        member_state: The EU member state whose rate is requested.
        kind: The rate tier (general / reduced / ...).
        on_date: The effective date for the lookup.

    Returns:
        The matching :class:`cadrumo.domain.iva.IvaRateRecord`.

    Raises:
        IvaRateNotFoundError: If no registered rate satisfies the query.
    """
    if not _member_state_is_registered(member_state):
        raise IvaRateNotFoundError(
            translated_message="errors.iva.rate_member_state_unregistered",
            context={
                "member_state": member_state.value,
                "member_state_registered": False,
                "rate_kind": kind.value,
                "on_date": on_date.isoformat(),
            },
        )
    if not _iva_rate_candidate_exists(member_state, kind, on_date):
        raise IvaRateNotFoundError(
            translated_message="errors.error.error_financial_iva_rate_not_found",
            context={
                "member_state": member_state.value,
                "member_state_registered": True,
                "rate_kind": kind.value,
                "on_date": on_date.isoformat(),
            },
        )
    return iva_rate_record_from_fact(resolve_iva_rate(member_state, kind, on_date))


def rate_table_covers(
    member_state: EUMemberState,
    on_date: date,
    kind: IvaRateKind | None = None,
) -> bool:
    """Return whether a tier-defining rate for ``member_state`` reaches ``on_date``.

    Coverage is PER TIER, and asking "any tier" answers a different question.
    The registry can hold a zero-tier record for a date while the general tier
    has none -- which is exactly the 2023 state after the RDL 20/2022 food rows
    landed. A caller resolving a 21 % line on such a date would be told the
    table covers it, fall through to the legality branch, and be handed the
    false "was not in force" claim again. Pass ``kind`` whenever the caller
    knows which tier it is asking about; ``None`` keeps the broad "can anything
    classify here" reading the ledger preflight wants.

    Separates the two reasons a rate lookup fails, which are not the same fact
    and must not produce the same message. The registry's ES coverage begins in
    2023 for the RDL 20/2022 food windows and 2024 for the standing tiers, so a
    2022 general-rate line fails not because its rate was unlawful -- Spain's
    21 % has stood since 2012 -- but because the table does not reach back that
    far. Whether the standing tiers' own start dates are correct is a separate
    open question: they assert 2024 for rates in force well before it.

    Telling a filer their rate "was not in force" when it plainly was sends
    them to correct a figure that was right, and invites widening the table
    with a guessed value. A regulatory value needs its own binding provision
    cited and corpus-backed, so a truthful refusal is the correct behaviour
    until those rows are authored.

    Reads only TIER-DEFINING records, skipping the coexisting temporary ones,
    because a date covered solely by a temporary window would misreport as
    uncovered. That cannot arise today -- every temporary window sits inside a
    year the tier-defining records already span -- and it is the safe direction
    regardless: the worse outcome is a refusal naming the rate rather than the
    year, not a line silently priced.

    Args:
        member_state: The member state whose table is queried.
        on_date: The date to test for coverage.
        kind: Restrict the question to one tier. ``None`` asks whether any
            tier-defining rate covers ``on_date``, which is a different and
            weaker claim -- see above.

    Returns:
        ``True`` when a tier-defining rate for ``kind`` (or for any tier when
        ``kind`` is ``None``) covers ``on_date``.
    """
    rates = tuple(iva_rate_record_from_fact(item) for item in _in_force_rate_facts(member_state, on_date))
    return any(
        not rate.supersedes_tier_default
        and (kind is None or rate.kind is kind)
        and rate.effective_from <= on_date
        and (rate.effective_until is None or on_date <= rate.effective_until)
        for rate in rates
    )


def rate_table_covers_any_positive_tier(member_state: EUMemberState, on_date: date) -> bool:
    """Return whether any POSITIVE ordinary tier is priced for ``member_state`` on ``on_date``.

    The question a caller resolving a positive declared rate must ask. A
    declared zero always classifies through the zero-tier exemption, so the
    zero tier's own coverage says nothing about whether a positive rate could
    have been priced. Counting it made a 2023 date look covered the moment the
    RDL 20/2022 food rows landed -- restoring the "unsupported rate" message
    on exactly the dates the coverage wording was written for.

    Lives beside the table it reads so both the ledger aggregation and the
    invoice path ask one authority rather than two predicates that can drift
    into disagreeing about the same date.

    Args:
        member_state: The member state whose table is queried.
        on_date: The date to test for coverage.

    Returns:
        ``True`` when a tier-defining rate for the general, reducido or
        super-reducido tier covers ``on_date``.
    """
    return any(
        rate_table_covers(member_state, on_date, kind)
        for kind in (IvaRateKind.GENERAL, IvaRateKind.REDUCED, IvaRateKind.SUPER_REDUCED)
    )


def coexisting_tier_rates(
    member_state: EUMemberState,
    kind: IvaRateKind,
    on_date: date,
) -> tuple[IvaRateRecord, ...]:
    """Return the rates coexisting with ``kind``'s ordinary rate on ``on_date``.

    Exactly the records :func:`lookup_rate` skips: those carrying
    :attr:`~cadrumo.domain.iva.IvaRateRecord.supersedes_tier_default`, which a
    statute put on PART of a tier's supplies while the rest stayed on the
    ordinary rate. :func:`lookup_rate` is right to skip them -- it answers "what
    is this tier's rate" and must answer with one number -- but skipping them
    silently leaves its caller unable to tell a tier with one rate from a tier
    that momentarily has two.

    This is the question that makes that distinction askable, so a caller
    deriving a number FROM a tier can refuse instead of returning the ordinary
    rate as though it were unambiguous. A non-empty result means the tier is
    ambiguous on that date and no goods axis in the bundled AEAT surfaces can
    separate the two populations.

    Args:
        member_state: The member state whose rates are searched.
        kind: The rate tier being interrogated.
        on_date: The date the coexisting rate must be in force.

    Returns:
        The in-force coexisting records, in registry declaration order. Empty
        when the tier carries only its ordinary rate on that date.
    """
    records = tuple(iva_rate_record_from_fact(rate) for rate in _in_force_rate_facts(member_state, on_date))
    return tuple(rate for rate in records if rate.kind is kind and rate.supersedes_tier_default)


def rate_kinds_for_declared_rate(
    member_state: EUMemberState,
    declared_rate: Decimal,
    on_date: date,
) -> tuple[IvaRateKind, ...]:
    """Return every tier whose registered rate equals ``declared_rate`` on ``on_date``.

    The inverse of :func:`lookup_rate`, and a genuinely different question. That
    one asks "what does this tier mean now" and must answer with exactly one
    rate; this asks "is this declared rate a legitimate one, and for which
    tier", which can legitimately have more than one answer -- a statute may put
    a temporary rate on part of a tier's supplies while the rest stay on the
    ordinary one, so 2 % and 4 % were both correct super-reducido rates in late
    2024 (RDL 4/2024 art. 1).

    Callers previously simulated this by iterating the tiers and calling
    :func:`lookup_rate` once each, comparing percentages. That works only while
    the tier-to-rate mapping is one-to-one per date, and silently stops finding
    a legitimate rate the moment a statute breaks that -- which is how a
    correctly-declared 2 % row came to be refused as an unsupported rate.

    Args:
        member_state: The member state whose rates are searched.
        declared_rate: The rate as a FRACTION (``Decimal("0.21")`` for 21 %),
            matching how a transaction stores it rather than how the registry
            does.
        on_date: The date the rate must have been in force.

    Returns:
        Matching tiers, ordered by their declaration in the registry. Empty when
        the rate was not a registered Spanish rate on that date -- which is a
        real refusal, not a lookup failure.
    """
    if not _member_state_is_registered(member_state):
        return ()
    matched: list[IvaRateKind] = []
    if declared_rate == Decimal("0"):
        # Zero is date-independent, and this is the one tier where the rate
        # table cannot answer the legality question at all.
        #
        # Spain zero-rates on FOUR distinct grounds, three of them permanent:
        # exports to a third country (LIVA art. 21), intra-community supplies
        # (art. 25), entregas of donativos to Ley 49/2002 entities
        # (art. 91.Cuatro), and the temporary RD-ley 4/2024 basic-foods window.
        # The authored rate schedule records only the last -- a flat ``kind =
        # "zero"`` record cannot be bounded to a class of supply, so an
        # open one would zero-rate everything. Reading that partial table as
        # exhaustive made every export and intra-EU supply unclassifiable
        # outside one 2024 quarter.
        #
        # So the honest answer is that 0 % is ALWAYS a legitimate Spanish
        # declared rate belonging to the ZERO tier, and whether THIS supply was
        # entitled to it is a question about the supply, not the rate. That
        # question lives on the category axis, which distinguishes
        # ``DOMESTIC_ZERO`` from ``EXPORT_THIRD_COUNTRY_ZERO_RATED`` and the
        # rest; the rate axis structurally cannot express it.
        matched.append(IvaRateKind.ZERO)
    for rate in (iva_rate_record_from_fact(item) for item in _in_force_rate_facts(member_state, on_date)):
        if rate.pct / Decimal("100") != declared_rate:
            continue
        if rate.kind not in matched:
            matched.append(rate.kind)
    return tuple(matched)


__all__ = ["coexisting_tier_rates", "lookup_rate", "rate_kinds_for_declared_rate", "resolve_iva_rate"]
