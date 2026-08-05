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

from ...iva import EUMemberState, IvaRateKind, load_iva_rate_table
from .._enums import IvaRate, iva_rate_kind, numeric_iva_rate_percentages

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
        kind
        for member in IvaRate
        if (kind := iva_rate_kind(member)) is not None and kind in _NUMERIC_RATE_KINDS
    )

    assert enum_kinds == registry_kinds, (
        "IvaRate numeric rate-kind coverage is out of sync with the registry.\n"
        f"  In enum but not registry: {sorted(k.value for k in enum_kinds - registry_kinds)}\n"
        f"  In registry but not enum: {sorted(k.value for k in registry_kinds - enum_kinds)}"
    )


def test_iva_rate_5_stays_intentionally_absent() -> None:
    """The transient 2022-2024 5% rate has no registry coverage in the served window, and no enum slot.

    Pins the ADR's stated invariant: ``RATE_5`` is absent from
    :class:`IvaRate` *because* the registry carries no ES rate window
    reaching :data:`_SERVED_WINDOW_START` at 5%. If a future registry
    ingestion adds pre-2025 ES coverage that reaches the served window at
    5%, ``test_iva_rate_numeric_members_match_registry_served_window`` fails
    first and this test documents why a new enum member would then be
    warranted.
    """
    assert Decimal("5") not in _registry_numeric_percentages_for_served_window()
    assert not hasattr(IvaRate, "RATE_5")


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

    registry_side_gains_a_rate = registry_percentages | {Decimal("5")}
    assert registry_side_gains_a_rate != enum_percentages

    enum_side_loses_a_rate = enum_percentages - {Decimal("21")}
    assert enum_side_loses_a_rate != registry_percentages
