"""Lookup helpers for IVA registry data.

:func:`lookup_rate` resolves :class:`EUMemberState` and :class:`IvaRateKind`
queries into :class:`IvaRateRecord` records projected from governed-fact
authority results; :func:`rate_table_covers`
answers whether the table reaches a date at all; :func:`cite` renders
:class:`IvaCategory` catalogue citations from an :class:`IvaCatalogue`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import TYPE_CHECKING, cast

from ..calculations.registry.eu_member_state_catalogue import require_eu_member_state
from ..calculations.registry.facts.resolution import (
    MappingFactQuery,
    ResolvedMappingFact,
    resolve_governed_fact,
)
from ..calculations.registry.facts.schema import FactSelector, GovernedFact, GovernedFactCatalogue
from ..calculations.registry.iva_rate_kind_catalogue import (
    require_iva_rate_kind,
    resolve_iva_rate_kind_catalogue,
)
from ..calculations.registry.iva_rate_role_catalogue import (
    IvaRateRole,
    require_iva_rate_role,
    resolve_iva_rate_role_catalogue,
)
from ..calculations.registry.schema_base import DateAxis
from .errors import IvaRateNotFoundError, IvaValidationError
from .rates import IVA_RATE_FACT_ID, iva_rate_record_from_fact
from .schema import EUMemberState, IvaRateKind, IvaRateRecord

if TYPE_CHECKING:
    from ..calculations.registry.authority import PinnedAuthorityOperation, ValidatedRegistryAuthority
    from ..calculations.registry.authority_artifact import AuthorityComponentReader, AuthorityGenerationPin
    from ..calculations.registry.facts.resolution import GovernedFactQuery, ResolvedGovernedFact
    from ..calculations.registry.governed_fact_scope import GovernedFactSource


def _authority(authority: ValidatedRegistryAuthority | None) -> ValidatedRegistryAuthority:
    """Require an explicitly supplied legacy validated authority."""
    if authority is None:
        raise IvaValidationError("IVA rate lookup requires an explicit authority operation or source")
    return authority


@dataclass(slots=True)
class _PinnedFactSource:
    """Resolve vocabulary dependencies from one caller-pinned component reader."""

    reader: AuthorityComponentReader
    generation: AuthorityGenerationPin
    _facts: dict[str, GovernedFact] = field(default_factory=dict)

    def _load_fact(self, fact_id: str) -> GovernedFact:
        cached = self._facts.get(fact_id)
        if cached is not None:
            return cached
        from ..calculations.registry.authority_artifact import GovernedFactComponentQuery

        component = self.reader.load(
            GovernedFactComponentQuery(fact_id=fact_id),
            pin=self.generation,
        )
        if not isinstance(component, GovernedFact) or component.fact_id != fact_id:
            raise ValueError(f"authority component reader returned an invalid governed fact for {fact_id!r}")
        self._facts[fact_id] = component
        return component

    def resolve_governed_fact(self, query: GovernedFactQuery) -> ResolvedGovernedFact:
        """Run the canonical dated resolver over the exact loaded declaration."""
        fact = self._load_fact(query.fact_id)
        return resolve_governed_fact(
            GovernedFactCatalogue(facts={fact.fact_id: fact}),
            query,
            authority_digest=self.generation.logical_generation,
        )


def resolve_iva_rate_from_component(
    reader: AuthorityComponentReader,
    *,
    pin: AuthorityGenerationPin,
    member_state: EUMemberState | str,
    kind: IvaRateKind,
    on_date: date,
    rate_role: IvaRateRole | str | None = None,
) -> ResolvedMappingFact:
    """Resolve one IVA rate through exact governed-fact components.

    The caller owns ``pin`` for the enclosing operation.  This function never
    repins, opens an eager catalogue, or substitutes bundled data when a
    component is unavailable.  Vocabulary facts and the requested
    ``iva-rate-schedule`` declaration are loaded through the same pinned
    reader, then the canonical dated resolver retains the reader generation in
    the returned provenance.
    """
    source = _PinnedFactSource(reader=reader, generation=pin)
    resolved_member_state = require_eu_member_state(member_state, effective_date=on_date, authority=source)
    resolved_kind = require_iva_rate_kind(kind, effective_date=on_date, authority=source)
    resolved_role = resolve_iva_rate_role_catalogue(
        effective_date=on_date,
        authority=source,
    ).require(rate_role)
    resolved = source.resolve_governed_fact(
        MappingFactQuery(
            fact_id=IVA_RATE_FACT_ID,
            date_axis=DateAxis.DEVENGO_DATE,
            effective_date=on_date,
            selectors=(
                FactSelector(name="member_state", value=resolved_member_state.value),
                FactSelector(name="kind", value=resolved_kind.value),
                FactSelector(name="rate_role", value=resolved_role.value),
            ),
        ),
    )
    if not isinstance(resolved, ResolvedMappingFact):
        raise ValueError("IVA rate fact must resolve as a mapping fact")
    return resolved


def resolve_iva_rate(
    member_state: EUMemberState,
    kind: IvaRateKind,
    on_date: date,
    *,
    rate_role: IvaRateRole | str | None = None,
    authority: GovernedFactSource | None = None,
    operation: PinnedAuthorityOperation | None = None,
) -> ResolvedMappingFact:
    """Resolve one dated IVA rate fact and retain the complete authority provenance."""
    if operation is not None:
        if authority is not None:
            raise TypeError("IVA rate resolution accepts either authority or operation, not both")
        return resolve_iva_rate_from_component(
            operation,
            pin=operation.pin(),
            member_state=member_state,
            kind=kind,
            on_date=on_date,
            rate_role=rate_role,
        )
    resolved_authority = _authority(cast("ValidatedRegistryAuthority | None", authority))
    kind = require_iva_rate_kind(kind, effective_date=on_date, authority=resolved_authority)
    role = require_iva_rate_role(rate_role, effective_date=on_date, authority=resolved_authority)
    resolved = resolved_authority.resolve_governed_fact(
        MappingFactQuery(
            fact_id=IVA_RATE_FACT_ID,
            date_axis=DateAxis.DEVENGO_DATE,
            effective_date=on_date,
            selectors=(
                FactSelector(name="member_state", value=member_state.value),
                FactSelector(name="kind", value=kind.value),
                FactSelector(name="rate_role", value=role.value),
            ),
        ),
    )
    return cast("ResolvedMappingFact", resolved)


def _member_state_is_registered(
    member_state: EUMemberState,
    *,
    authority: GovernedFactSource | None = None,
    operation: PinnedAuthorityOperation | None = None,
) -> bool:
    """Return whether the rate fact declares any variant for ``member_state``."""
    if operation is not None and authority is not None:
        raise TypeError("IVA rate membership accepts either authority or operation, not both")
    if operation is not None:
        fact = operation.governed_fact(IVA_RATE_FACT_ID)
    else:
        resolved_authority = _authority(cast("ValidatedRegistryAuthority | None", authority))
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
    rate_role: IvaRateRole | str | None = None,
    authority: GovernedFactSource | None = None,
    operation: PinnedAuthorityOperation | None = None,
) -> bool:
    """Separate a genuine absence from an ambiguous authority resolution."""
    if operation is not None and authority is not None:
        raise TypeError("IVA rate candidate lookup accepts either authority or operation, not both")
    if operation is not None:
        role = resolve_iva_rate_role_catalogue(effective_date=on_date, authority=operation).require(rate_role)
        fact = operation.governed_fact(IVA_RATE_FACT_ID)
    else:
        resolved_authority = _authority(cast("ValidatedRegistryAuthority | None", authority))
        resolved_authority.validate_registry()
        role = require_iva_rate_role(rate_role, effective_date=on_date, authority=resolved_authority)
        fact = resolved_authority.catalogues.facts.facts.get(IVA_RATE_FACT_ID)
    if fact is None:
        return False
    expected = {
        "member_state": member_state.value,
        "kind": kind.value,
        "rate_role": role.value,
    }
    return any(
        variant.date_axis is DateAxis.DEVENGO_DATE
        and variant.valid_from is not None
        and variant.valid_from <= on_date
        and (variant.valid_to is None or on_date <= variant.valid_to)
        and {selector.name: selector.value for selector in variant.selectors} == expected
        for variant in fact.variants
    )


def _in_force_rate_facts(
    member_state: EUMemberState,
    on_date: date,
    *,
    authority: GovernedFactSource | None = None,
    operation: PinnedAuthorityOperation | None = None,
) -> tuple[ResolvedMappingFact, ...]:
    """Resolve every IVA fact variant in force for a member state at one devengo date."""
    if operation is not None and authority is not None:
        raise TypeError("IVA rate enumeration accepts either authority or operation, not both")
    if operation is not None:
        selected_authority = None
        fact = operation.governed_fact(IVA_RATE_FACT_ID)
    else:
        selected_authority = _authority(cast("ValidatedRegistryAuthority | None", authority))
        selected_authority.validate_registry()
        fact = selected_authority.catalogues.facts.facts.get(IVA_RATE_FACT_ID)
    if fact is None:
        return ()
    candidates = tuple(
        variant
        for variant in fact.variants
        if variant.date_axis is DateAxis.DEVENGO_DATE
        and variant.valid_from is not None
        and variant.valid_from <= on_date
        and (variant.valid_to is None or on_date <= variant.valid_to)
        and {selector.name: selector.value for selector in variant.selectors}.get("member_state") == member_state.value
    )
    resolved_rates: list[ResolvedMappingFact] = []
    for variant in candidates:
        selectors = {selector.name: selector.value for selector in variant.selectors}
        if operation is not None:
            kind = require_iva_rate_kind(str(selectors["kind"]), effective_date=on_date, authority=operation)
            resolved_rates.append(
                resolve_iva_rate(
                    member_state,
                    kind,
                    on_date,
                    rate_role=str(selectors["rate_role"]),
                    operation=operation,
                )
            )
        else:
            if selected_authority is None:
                raise IvaValidationError("IVA rate enumeration has no selected authority")
            kind = require_iva_rate_kind(str(selectors["kind"]), effective_date=on_date, authority=selected_authority)
            resolved_rates.append(
                resolve_iva_rate(
                    member_state,
                    kind,
                    on_date,
                    rate_role=str(selectors["rate_role"]),
                    authority=selected_authority,
                )
            )
    return tuple(resolved_rates)


def lookup_rate(
    member_state: EUMemberState,
    kind: IvaRateKind,
    on_date: date,
    *,
    authority: GovernedFactSource | None = None,
    operation: PinnedAuthorityOperation | None = None,
) -> IvaRateRecord:
    """Return the :class:`cadrumo.domain.iva.IvaRateRecord` matching the supplied query.

    Resolves the ordinary governed-fact variant for the exact member-state,
    tier, and devengo-date coordinates, then projects it onto the established
    public record.

    Args:
        member_state: The EU member state whose rate is requested.
        kind: The rate tier (general / reduced / ...).
        on_date: The effective date for the lookup.
        authority: Explicit governed-fact source for the lookup. Mutually
            exclusive with ``operation``.
        operation: Caller-owned pinned authority operation for the complete
            lookup. Mutually exclusive with ``authority``.

    Returns:
        The matching :class:`cadrumo.domain.iva.IvaRateRecord`.

    Raises:
        IvaRateNotFoundError: If no registered rate satisfies the query.
    """
    if operation is not None and authority is not None:
        raise TypeError("IVA rate lookup accepts either authority or operation, not both")
    selected_authority = operation or authority
    kind = require_iva_rate_kind(kind, effective_date=on_date, authority=selected_authority)
    if not _member_state_is_registered(member_state, authority=authority, operation=operation):
        raise IvaRateNotFoundError(
            translated_message="errors.iva.rate_member_state_unregistered",
            context={
                "member_state": member_state.value,
                "member_state_registered": False,
                "rate_kind": kind.value,
                "on_date": on_date.isoformat(),
            },
        )
    if not _iva_rate_candidate_exists(member_state, kind, on_date, authority=authority, operation=operation):
        raise IvaRateNotFoundError(
            translated_message="errors.error.error_financial_iva_rate_not_found",
            context={
                "member_state": member_state.value,
                "member_state_registered": True,
                "rate_kind": kind.value,
                "on_date": on_date.isoformat(),
            },
        )
    return iva_rate_record_from_fact(
        resolve_iva_rate(
            member_state,
            kind,
            on_date,
            authority=authority if operation is None else None,
            operation=operation,
        ),
        authority=selected_authority,
    )


def rate_table_covers(
    member_state: EUMemberState,
    on_date: date,
    kind: IvaRateKind | None = None,
    *,
    authority: GovernedFactSource | None = None,
    operation: PinnedAuthorityOperation | None = None,
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
        authority: Explicit governed-fact source for the coverage query.
            Mutually exclusive with ``operation``.
        operation: Caller-owned pinned authority operation for the complete
            coverage query. Mutually exclusive with ``authority``.

    Returns:
        ``True`` when a tier-defining rate for ``kind`` (or for any tier when
        ``kind`` is ``None``) covers ``on_date``.
    """
    if kind is not None:
        kind = require_iva_rate_kind(kind, effective_date=on_date, authority=operation or authority)
    rates = tuple(
        iva_rate_record_from_fact(item, authority=operation or authority)
        for item in _in_force_rate_facts(member_state, on_date, authority=authority, operation=operation)
    )
    return any(
        not rate.supersedes_tier_default
        and (kind is None or rate.kind == kind)
        and rate.effective_from <= on_date
        and (rate.effective_until is None or on_date <= rate.effective_until)
        for rate in rates
    )


def rate_table_covers_any_positive_tier(
    member_state: EUMemberState,
    on_date: date,
    *,
    authority: GovernedFactSource | None = None,
    operation: PinnedAuthorityOperation | None = None,
) -> bool:
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
        authority: Explicit governed-fact source for the coverage query.
            Mutually exclusive with ``operation``.
        operation: Caller-owned pinned authority operation for the complete
            coverage query. Mutually exclusive with ``authority``.

    Returns:
        ``True`` when a tier-defining rate for the general, reducido or
        super-reducido tier covers ``on_date``.
    """
    return any(
        rate_table_covers(member_state, on_date, kind, authority=authority, operation=operation)
        for kind in resolve_iva_rate_kind_catalogue(
            effective_date=on_date, authority=operation or authority
        ).positive_kinds
    )


def coexisting_tier_rates(
    member_state: EUMemberState,
    kind: IvaRateKind,
    on_date: date,
    *,
    authority: GovernedFactSource | None = None,
    operation: PinnedAuthorityOperation | None = None,
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
        authority: Explicit governed-fact source for the query. Mutually
            exclusive with ``operation``.
        operation: Caller-owned pinned authority operation for the complete
            query. Mutually exclusive with ``authority``.

    Returns:
        The in-force coexisting records, in registry declaration order. Empty
        when the tier carries only its ordinary rate on that date.
    """
    kind = require_iva_rate_kind(kind, effective_date=on_date, authority=operation or authority)
    records = tuple(
        iva_rate_record_from_fact(rate, authority=operation or authority)
        for rate in _in_force_rate_facts(member_state, on_date, authority=authority, operation=operation)
    )
    return tuple(rate for rate in records if rate.kind == kind and rate.supersedes_tier_default)


def rate_kinds_for_declared_rate(
    member_state: EUMemberState,
    declared_rate: Decimal,
    on_date: date,
    *,
    authority: GovernedFactSource | None = None,
    operation: PinnedAuthorityOperation | None = None,
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
        authority: Explicit governed-fact source for the query. Mutually
            exclusive with ``operation``.
        operation: Caller-owned pinned authority operation for the complete
            query. Mutually exclusive with ``authority``.

    Returns:
        Matching tiers, ordered by their declaration in the registry. Empty when
        the rate was not a registered Spanish rate on that date -- which is a
        real refusal, not a lookup failure.
    """
    if not _member_state_is_registered(member_state, authority=authority, operation=operation):
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
        matched.append(
            resolve_iva_rate_kind_catalogue(effective_date=on_date, authority=operation or authority).zero_token,
        )
    for rate in (
        iva_rate_record_from_fact(item, authority=operation or authority)
        for item in _in_force_rate_facts(member_state, on_date, authority=authority, operation=operation)
    ):
        if rate.pct / Decimal("100") != declared_rate:
            continue
        if rate.kind not in matched:
            matched.append(rate.kind)
    return tuple(matched)


__all__ = [
    "coexisting_tier_rates",
    "lookup_rate",
    "rate_kinds_for_declared_rate",
    "resolve_iva_rate",
    "resolve_iva_rate_from_component",
]
