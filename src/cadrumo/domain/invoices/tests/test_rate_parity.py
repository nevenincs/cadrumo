"""Parity gate binding :class:`cadrumo.domain.invoices.IvaRate` to the registry rate table.

:class:`~cadrumo.domain.invoices.IvaRate`'s numeric slots (``RATE_0``,
``RATE_4``, ``RATE_10``, ``RATE_21``) are a closed taxonomy that must stay in
lock-step with the numeric Spanish rate kinds
:func:`cadrumo.domain.iva.load_iva_rate_table` actually resolves for the
served window (the range the registry declares coverage for; ES rows start
``2024-01-01``, see ``test_lookup_rate_respects_effective_from`` in
``cadrumo.domain.iva.tests.test_rates``). A registry rate added with no
matching enum slot, or an enum slot the registry can no longer resolve, must
fail loudly here rather than surface downstream as an unrepresentable line or
a silently unresolved percentage.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from ...iva import EUMemberState, IvaRateKind, IvaRateNotFoundError, load_iva_rate_table, lookup_rate
from ..enums import (
    IvaRate,
    iva_rate_kind,
    iva_rate_percentage,
    numeric_iva_rate_percentages,
    numeric_iva_rate_slots,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_SERVED_WINDOW_START = date(2024, 1, 1)
"""Earliest date the registry's ES rate coverage resolves.

Matches the boundary ``test_lookup_rate_respects_effective_from``
(``cadrumo.domain.iva.tests.test_rates``) pins: a lookup dated before this is
refused with :class:`~cadrumo.domain.iva.IvaRateNotFoundError`, so nothing
before it is part of the "served window" this gate reconciles against.
"""

_NUMERIC_RATE_KINDS = frozenset(
    {
        IvaRateKind.GENERAL,
        IvaRateKind.REDUCED,
        IvaRateKind.SUPER_REDUCED,
        IvaRateKind.ZERO,
    },
)
"""Registry rate tiers that carry a percentage an invoice line can declare.

``IvaRateKind.EXEMPT`` has no percentage; it is represented on
:class:`IvaRate` by the non-numeric ``EXEMPT`` slot, out of scope for this
numeric-percentage parity gate.
"""


def _registry_numeric_percentages_for_served_window() -> frozenset[Decimal]:
    """Return the numeric ES rate percentages the registry declares for the served window.

    Reads every Spanish :class:`~cadrumo.domain.iva.IvaRateRecord` whose
    ``kind`` is numeric and whose validity window has not closed before
    :data:`_SERVED_WINDOW_START`, i.e. every rate an invoice dated inside the
    served window could actually resolve through
    :func:`cadrumo.domain.iva.lookup_rate`.
    """
    es_rates = load_iva_rate_table()[EUMemberState.ES]
    return frozenset(
        rate.pct
        for rate in es_rates
        if rate.kind in _NUMERIC_RATE_KINDS
        and (rate.effective_until is None or rate.effective_until >= _SERVED_WINDOW_START)
    )


def _registry_numeric_kinds_for_served_window() -> frozenset[IvaRateKind]:
    """Return the numeric ES rate kinds the registry declares for the served window."""
    es_rates = load_iva_rate_table()[EUMemberState.ES]
    return frozenset(
        rate.kind
        for rate in es_rates
        if rate.kind in _NUMERIC_RATE_KINDS
        and (rate.effective_until is None or rate.effective_until >= _SERVED_WINDOW_START)
    )


def test_iva_rate_numeric_members_match_registry_served_window() -> None:
    """:func:`numeric_iva_rate_percentages` equals the registry's ES numeric rate set.

    Both sides are read from their own authority (the enum's ``RATE_<n>``
    member names; the registry's ``rates.toml`` rows) with no shared literal
    between them, so agreement is a genuine cross-check rather than a
    restatement of one side.
    """
    registry_percentages = _registry_numeric_percentages_for_served_window()
    enum_percentages = numeric_iva_rate_percentages()

    assert enum_percentages == registry_percentages, (
        "IvaRate numeric members are out of sync with the registry ES rate table "
        "for the served window.\n"
        f"  In enum but not registry: {sorted(enum_percentages - registry_percentages)}\n"
        f"  In registry but not enum: {sorted(registry_percentages - enum_percentages)}"
    )


def test_iva_rate_numeric_kinds_match_registry_served_window() -> None:
    """Every :class:`IvaRate` numeric slot maps to a registry kind the served window resolves, and no more."""
    registry_kinds = _registry_numeric_kinds_for_served_window()
    enum_kinds = frozenset(
        kind for member in IvaRate if (kind := iva_rate_kind(member)) is not None and kind in _NUMERIC_RATE_KINDS
    )

    assert enum_kinds == registry_kinds, (
        "IvaRate numeric rate-kind coverage is out of sync with the registry.\n"
        f"  In enum but not registry: {sorted(k.value for k in enum_kinds - registry_kinds)}\n"
        f"  In registry but not enum: {sorted(k.value for k in registry_kinds - enum_kinds)}"
    )


def test_the_transitional_food_rates_have_slots_because_the_registry_serves_them() -> None:
    """The RD-ley 4/2024 phase-out rates are nameable, and for the stated reason.

    This assertion previously held the opposite: ``RATE_5`` was absent
    *because* no ES window reached the served window at 5%. Registry coverage
    for 2024 changed that premise -- 2%, 5% and 7.5% are all served inside the
    window -- so the enum gained the slots rather than the gate being relaxed.

    Kept rather than deleted, and inverted, because the reasoning is the part
    worth pinning: a rate the registry can resolve for a dated invoice must
    have a slot, or that line cannot be recorded truthfully. A 2024 filing is
    still amendable, so these are live slots, not historical decoration.

    Each is checked against the tier it modifies, not merely for presence: the
    RD-ley reduces specific foodstuffs within the existing LIVA tiers, so a
    transitional rate that mapped to the wrong kind would resolve a different
    percentage for the same date.
    """
    served = _registry_numeric_percentages_for_served_window()
    slots = numeric_iva_rate_slots()

    for pct, expected_kind in (
        (Decimal("2"), IvaRateKind.SUPER_REDUCED),
        (Decimal("5"), IvaRateKind.REDUCED),
        (Decimal("7.5"), IvaRateKind.REDUCED),
    ):
        assert pct in served, f"{pct}% is no longer served; this test's premise has moved again"
        assert pct in slots, f"the registry serves {pct}% but no IvaRate slot can name it"
        assert iva_rate_kind(slots[pct]) is expected_kind, (
            f"{pct}% must map to {expected_kind.value}: it is a transitional reduction WITHIN that "
            "LIVA tier, and a wrong kind resolves a different percentage for the same date"
        )


def test_every_numeric_slot_resolves_to_the_percentage_it_names() -> None:
    """A slot's resolved percentage equals its own name, never its tier's ordinary rate.

    The gap this closes let a green suite ship a silent over-declaration.
    Membership parity and tier parity above both passed while
    :func:`iva_rate_percentage` resolved ``RATE_2`` to 4 % and ``RATE_7_5`` to
    10 %: it asked :func:`~cadrumo.domain.iva.lookup_rate` what the slot's TIER
    meant, and that function skips ``supersedes_tier_default`` records by
    design, so it answered with the ordinary rate the transitional one
    coexists with. A 2 % foodstuffs line computed twice the IVA it carried.

    Nothing above can catch that, because both existing gates compare SETS --
    of percentages and of tiers -- and never resolve a slot. This asserts the
    resolution itself, per slot, on a date each is in force.
    """
    for slot_date in (date(2024, 8, 15), date(2024, 11, 15), date(2025, 6, 1)):
        for percentage, member in numeric_iva_rate_slots().items():
            try:
                resolved = iva_rate_percentage(member, slot_date)
            except IvaRateNotFoundError:
                # Correct for a transitional slot outside its window; the
                # refusal itself is pinned by the window test below.
                continue
            assert resolved == percentage / Decimal("100"), (
                f"{member.name} resolved to {resolved} on {slot_date.isoformat()}, but the slot names "
                f"{percentage}%. A slot must resolve its OWN rate -- resolving its tier's ordinary rate "
                "records a number the line never carried."
            )


def test_transitional_slots_refuse_outside_their_statutory_window() -> None:
    """The RD-ley 4/2024 slots resolve inside their window and are refused outside it.

    The window is the whole reason these slots can carry their own number
    safely: 2 % and 4 % were both correct super-reducido rates in late 2024, so
    a slot that resolved regardless of date would let a 2025 invoice claim a
    rate the statute had already withdrawn. Refusal is the honest answer --
    substituting the tier's ordinary rate would silently record 4 % on a line
    the operator marked 2 %.
    """
    inside = date(2024, 11, 15)
    outside = date(2025, 6, 1)

    assert iva_rate_percentage(IvaRate.RATE_2, inside) == Decimal("0.02")
    assert iva_rate_percentage(IvaRate.RATE_7_5, inside) == Decimal("0.075")
    # 5 % ran to 2024-09-30 and was already superseded by 7,5 % in November.
    assert iva_rate_percentage(IvaRate.RATE_5, date(2024, 8, 15)) == Decimal("0.05")

    for member in (IvaRate.RATE_2, IvaRate.RATE_5, IvaRate.RATE_7_5):
        with pytest.raises(IvaRateNotFoundError):
            iva_rate_percentage(member, outside)

    # The standing slots are unaffected by the window and keep resolving.
    assert iva_rate_percentage(IvaRate.RATE_21, outside) == Decimal("0.21")
    assert iva_rate_percentage(IvaRate.RATE_4, outside) == Decimal("0.04")


def test_a_zero_rated_line_resolves_on_every_date_the_registry_cannot_speak_for() -> None:
    """RATE_0 must never be refused for want of a registry zero record.

    This pins a live defect, not a hypothetical. The in-force check resolves a
    slot against the registry, and the ES zero coverage is deliberately partial:
    ``rates.toml`` registers only the RD-ley 4/2024 zero window and states in its
    own comment that the indefinite art. 91.Cuatro 0 % (entregas de donativos,
    Ley 49/2002) is intentionally NOT registered, because a flat ``kind = "zero"``
    record cannot be bounded to donativos and an open one would zero-rate every
    domestic supply.

    A missing zero record therefore means "this registry cannot say", not "no
    zero-rated supply was lawful that day". Testing in-force against it refused
    RATE_0 at EVERY date, which made a zero-rated invoice unrecordable outside a
    single 2024 quarter -- while the CLI still offered the slot.

    The dates span all three regions deliberately: before the registered zero
    window, inside it, and long after. Only the middle one has a record, so the
    other two are the ones that were failing.
    """
    for on_date in (date(2024, 3, 15), date(2024, 8, 15), date(2026, 6, 1)):
        assert iva_rate_percentage(IvaRate.RATE_0, on_date) == Decimal("0"), (
            f"RATE_0 must resolve on {on_date.isoformat()}: the registry's silence about a zero tier is "
            "incomplete coverage, not a statement that zero-rating was unlawful"
        )


def test_slot_resolution_gate_would_catch_a_tier_default_substitution() -> None:
    """Mutation proof for the resolution gate: it fails when a slot resolves its tier's rate.

    Re-derives what the pre-fix implementation returned -- the tier's ordinary
    rate via :func:`~cadrumo.domain.iva.lookup_rate` -- and confirms the
    assertion above rejects it. Without this, a future refactor that quietly
    routed resolution back through the tier would pass a gate that only ever
    compared each slot against itself.
    """
    on_date = date(2024, 11, 15)
    slots = numeric_iva_rate_slots()

    # A tier the registry cannot resolve on this date is skipped rather than
    # allowed to raise. The ZERO tier is exactly that: rates.toml registers only
    # the RD-ley 4/2024 zero window and deliberately omits the indefinite
    # art. 91.Cuatro 0%, so lookup_rate refuses for it. That is a gap in the
    # substitution being probed, not a slot escaping the probe -- RATE_0 names
    # 0 % and no tier default could differ from it anyway.
    tier_substituted: dict[IvaRate, Decimal] = {}
    for member in slots.values():
        kind = iva_rate_kind(member)
        if kind is None:
            continue
        try:
            tier_substituted[member] = lookup_rate(EUMemberState.ES, kind, on_date).pct / Decimal("100")
        except IvaRateNotFoundError:
            continue

    disagreeing = {
        member.name
        for percentage, member in slots.items()
        if member in tier_substituted and tier_substituted[member] != percentage / Decimal("100")
    }
    # Every coexisting slot disagrees, including RATE_5, whose window had
    # already closed by this date -- the tier lookup answers regardless of the
    # slot's own window, which is the second half of why it cannot be trusted
    # to supply the number. The standing slots agree, so the substitution was
    # invisible until a coexisting rate existed.
    assert disagreeing == {"RATE_2", "RATE_5", "RATE_7_5"}, (
        "the tier-substitution the fix removed must still be observable and still wrong for exactly the "
        f"coexisting slots; got {sorted(disagreeing)}"
    )


def test_parity_gate_discriminates_on_either_side() -> None:
    """Mutation proof: the equality gate is not vacuously true.

    Confirms the two independently-sourced sets genuinely agree today, then
    proves the comparison used by
    ``test_iva_rate_numeric_members_match_registry_served_window`` flips from
    equal to unequal when either side is perturbed by a single member — the
    gate would catch a registry addition the enum has not caught up with, and
    would catch an enum addition the registry cannot resolve.
    """
    registry_percentages = _registry_numeric_percentages_for_served_window()
    enum_percentages = numeric_iva_rate_percentages()

    assert enum_percentages == registry_percentages, "baseline agreement must hold before mutating either side"

    # Perturb with a percentage no Spanish IVA tier has ever carried. Using a
    # real rate would silently stop mutating the moment the registry gained it,
    # which is exactly what happened when this line used 5%.
    absent_rate = Decimal("3")
    assert absent_rate not in registry_percentages, "pick a rate outside the taxonomy, or this proves nothing"
    registry_side_gains_a_rate = registry_percentages | {absent_rate}
    assert registry_side_gains_a_rate != enum_percentages

    enum_side_loses_a_rate = enum_percentages - {Decimal("21")}
    assert enum_side_loses_a_rate != registry_percentages
