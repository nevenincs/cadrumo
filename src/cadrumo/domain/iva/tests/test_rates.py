"""Unit tests for the EU IVA rate table exposed by :mod:`cadrumo.domain.iva`.

Covers the 27-state coverage invariant, the Spanish multi-tier expansion, the
:func:`cadrumo.domain.iva.lookup_rate` happy and error paths, and the per-record
window well-orderedness invariant.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from cadrumo.domain.calculations.registry.authority import bundled_indexed_authority as _indexed_authority_for_test

from ..errors import IvaRateNotFoundError
from ..lookup import lookup_rate
from ..rates import load_iva_rate_table
from ..schema import EUMemberState, IvaRateKind

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def test_rate_table_covers_all_27_member_states() -> None:
    """The rate table carries entries for EU member states, not the XI prefix."""
    with _indexed_authority_for_test().operation() as _authority_operation_for_test:
        expected = {member for member in EUMemberState if member is not EUMemberState._from_registry("xi")}
        assert set(load_iva_rate_table(operation=_authority_operation_for_test).keys()) == expected
        assert EUMemberState._from_registry("xi") not in load_iva_rate_table(operation=_authority_operation_for_test)


def test_lookup_rate_raises_for_northern_ireland_prefix() -> None:
    """XI is a Modelo 349 goods prefix, not a rate-table jurisdiction.

    Pinned on the refusal's key and machine facts rather than on rendered
    prose: the offending jurisdiction reaches the operator through
    ``context``, which every locale carries identically, while a substring of
    an English sentence is readable in one locale only.
    """
    with _indexed_authority_for_test().operation() as _authority_operation_for_test:
        with pytest.raises(IvaRateNotFoundError) as caught:
            lookup_rate(
                EUMemberState._from_registry("xi"),
                IvaRateKind("general"),
                date(2025, 6, 1),
                operation=_authority_operation_for_test,
            )

        assert caught.value.translated_message == "errors.iva.rate_member_state_unregistered"
        assert caught.value.context == {
            "member_state": "xi",
            "member_state_registered": False,
            "rate_kind": IvaRateKind("general").value,
            "on_date": "2025-06-01",
        }


def test_rate_table_has_at_least_50_entries() -> None:
    """Aggregate rate count must meet the at-least-50-entries acceptance threshold."""
    with _indexed_authority_for_test().operation() as _authority_operation_for_test:
        total = sum(len(rates) for rates in load_iva_rate_table(operation=_authority_operation_for_test).values())
        assert total >= 50


def test_es_rate_table_fully_expanded() -> None:
    """Spain must expose general / reduced / super_reduced / zero tiers."""
    with _indexed_authority_for_test().operation() as _authority_operation_for_test:
        es_kinds = {
            rate.kind
            for rate in load_iva_rate_table(operation=_authority_operation_for_test)[EUMemberState._from_registry("es")]
        }
        assert {
            IvaRateKind("general"),
            IvaRateKind("reduced"),
            IvaRateKind("super_reduced"),
            IvaRateKind("zero"),
        } <= es_kinds


def test_lookup_rate_returns_spain_general_21() -> None:
    """`lookup_rate` resolves the Spanish general rate for mid-2025."""
    with _indexed_authority_for_test().operation() as _authority_operation_for_test:
        rate = lookup_rate(
            EUMemberState._from_registry("es"),
            IvaRateKind("general"),
            date(2025, 6, 1),
            operation=_authority_operation_for_test,
        )
        assert rate.pct == Decimal("21")


def test_lookup_rate_raises_for_unknown_kind() -> None:
    """Denmark has no reduced rate; lookup must raise.

    ``member_state_registered`` is the fact that separates this refusal from
    the XI one above: Denmark IS in the table and simply carries no reducido
    tier, while XI is absent from the table outright. The two conditions must
    stay separable by machine fact, not only by prose.
    """
    with _indexed_authority_for_test().operation() as _authority_operation_for_test:
        with pytest.raises(IvaRateNotFoundError) as caught:
            lookup_rate(
                EUMemberState._from_registry("dk"),
                IvaRateKind("reduced"),
                date(2025, 6, 1),
                operation=_authority_operation_for_test,
            )

        assert caught.value.translated_message == "errors.error.error_financial_iva_rate_not_found"
        assert caught.value.context == {
            "member_state": "dk",
            "member_state_registered": True,
            "rate_kind": IvaRateKind("reduced").value,
            "on_date": "2025-06-01",
        }


def test_lookup_rate_respects_effective_from() -> None:
    """Rates dated before the earliest registered window must not match.

    The probe moved from 2023 to 2012-08-31 when the ES general window was
    corrected: 2023 refused because ``effective_from`` carried a bulk-refresh
    boundary rather than the legal one, so asserting it pinned an artefact. The
    property under test is unchanged -- a date before the earliest window
    refuses -- and it now sits on the boundary the statute actually sets, the
    day before RDL 20/2012 art. 23.Dos took effect.
    """
    with _indexed_authority_for_test().operation() as _authority_operation_for_test:
        with pytest.raises(IvaRateNotFoundError, match=r"ES|GENERAL|2012|rate"):
            lookup_rate(
                EUMemberState._from_registry("es"),
                IvaRateKind("general"),
                date(2012, 8, 31),
                operation=_authority_operation_for_test,
            )


def test_every_rate_window_is_well_ordered() -> None:
    """Every :class:`IvaRateRecord` with both bounds set must satisfy ``effective_from <= effective_until``."""
    with _indexed_authority_for_test().operation() as _authority_operation_for_test:
        for rates in load_iva_rate_table(operation=_authority_operation_for_test).values():
            for rate in rates:
                if rate.effective_until is not None:
                    assert rate.effective_from <= rate.effective_until
