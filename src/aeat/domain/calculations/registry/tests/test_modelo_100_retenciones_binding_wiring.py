"""Regression guard: M111 → casilla 0596 and M123 → casilla 0597 binding wiring.

Before this fix, casillas 0596 and 0597 in the 2024 revision had no
``input_kind = "bound"`` and no ``binding`` field, so
``_resolve_bound_casilla_inputs_for_available_bindings`` silently skipped them.
The binding value was accepted without error but never reached the formula engine,
so 0609 (total pagos a cuenta) and 0610 (cuota diferencial) were computed wrong.

Binding-to-casilla plumbing contract (not a formula derivation):
  - binding ``renta-2024-modelo-111-retenciones-periodicas`` → casilla 0596
  - binding ``renta-2024-modelo-123-retenciones-periodicas`` → casilla 0597

The expected value for 0596 / 0597 IS the binding value by definition — the
binding declares ``aggregation.op = "sum"`` over the previous-filing source and
the casilla inherits that sum directly.  Asserting 0597 == binding value is
therefore NOT tautological: it tests whether the registry plumbing connects
(previously broken: 0597 == 0 regardless of binding); the formula 0609 = Σ
operands provides independent confirmation that the wired value propagates.

Oracle for anti-tautology test: without custodia changes, 0597 MUST equal the
supplied binding value and MUST NOT stay at zero.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from .. import RegistrySnapshot, calculate_registry_snapshot
from .._authority import ValidatedRegistryAuthority

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_DATE_CONTEXT_2024 = {"filing_period": date(2024, 12, 31)}
_DATE_BINDINGS_2024 = {"renta-2024-profile-taxpayer-birth-date": date(1975, 6, 15)}

_RELATION_VALUES_2024 = {
    "renta-2024-rel-111-retenciones-trimestrales": Decimal("0"),
    "renta-2024-rel-111-retenciones-mensuales": Decimal("0"),
    "renta-2024-rel-115-retenciones-trimestrales": Decimal("0"),
    "renta-2024-rel-123-retenciones-trimestrales": Decimal("0"),
    "renta-2024-rel-193-retenciones-anuales": Decimal("0"),
    "renta-2024-rel-130-pagos-fraccionados": Decimal("0"),
    "renta-2024-rel-131-pagos-fraccionados": Decimal("0"),
}


def _base_binding_values(*, m111: Decimal = Decimal("0"), m123: Decimal = Decimal("0")) -> dict:
    return {
        "renta-2024-modelo-100-estimacion-directa-es-normal": Decimal("1"),
        "renta-2024-modelo-111-retenciones-periodicas": m111,
        "renta-2024-modelo-115-retenciones-periodicas": Decimal("0"),
        "renta-2024-modelo-123-retenciones-periodicas": m123,
        "renta-2024-modelo-193-retenciones-anuales": Decimal("0"),
        "renta-2024-profile-declaration-type": Decimal("1"),
        "renta-2024-profile-family-minor-children-in-unit": Decimal("0"),
        # Art. 81 bis LIRPF guarderia bindings (b7ad3a993): zero in non-guarderia scenarios.
        "renta-2024-profile-guarderia-gastos-reales": Decimal("0"),
        "renta-2024-profile-cotizaciones-ss-madre": Decimal("0"),
        "renta-2024-profile-descendientes-menores-3": Decimal("0"),
        "renta-2024-profile-marriage-full-year": Decimal("0"),
        "renta-2024-profile-marriage-month-start": Decimal("0"),
        "renta-2024-profile-marriage-month-end": Decimal("0"),
        # BIN-pendiente fresh-filer baseline.
        "renta-2024-base-liquidable-negativa-general-anterior": Decimal("0"),
    }


@pytest.fixture
def m100_2024_snapshot(registry_authority: ValidatedRegistryAuthority):
    return registry_authority.snapshot("100", filing_year=2024, period="0A")


def test_m123_retenciones_binding_populates_casilla_0597(m100_2024_snapshot: RegistrySnapshot) -> None:
    """Binding renta-2024-modelo-123-retenciones-periodicas must land in casilla 0597.

    Regression guard for Sergio round-13 C3: with the 2024 casilla missing
    ``input_kind = "bound"`` and ``binding = "..."``, the engine skipped 0597
    and it stayed at zero regardless of the binding value supplied.

    Wiring contract: 0597 == binding value (direct pass-through; no formula
    transforms the binding before it lands in the casilla).
    """
    m123_retenciones = Decimal("3800.00")
    result = calculate_registry_snapshot(
        m100_2024_snapshot,
        inputs={"0003": Decimal("0")},
        date_context=_DATE_CONTEXT_2024,
        enum_binding_values={"renta-2024-profile-tax-residence-ccaa": "madrid"},
        binding_values=_base_binding_values(m123=m123_retenciones),
        relation_values=_RELATION_VALUES_2024,
        date_binding_values=_DATE_BINDINGS_2024,
    )

    assert result.values["0597"] == m123_retenciones, (
        f"casilla 0597 = {result.values['0597']!r}; expected {m123_retenciones!r} "
        f"from binding renta-2024-modelo-123-retenciones-periodicas. "
        "Check 2024/casillas/0579-0597.toml: must have "
        'input_kind = "bound" and binding = "renta-2024-modelo-123-retenciones-periodicas".'
    )


def test_m111_retenciones_binding_populates_casilla_0596(m100_2024_snapshot: RegistrySnapshot) -> None:
    """Binding renta-2024-modelo-111-retenciones-periodicas must land in casilla 0596.

    M111 (trabajo retenciones) shares the same structural gap as M123:
    without ``input_kind = "bound"`` + ``binding`` on casilla 0596, the
    binding is accepted but silently dropped.
    """
    m111_retenciones = Decimal("6000.00")
    result = calculate_registry_snapshot(
        m100_2024_snapshot,
        inputs={"0003": Decimal("0")},
        date_context=_DATE_CONTEXT_2024,
        enum_binding_values={"renta-2024-profile-tax-residence-ccaa": "madrid"},
        binding_values=_base_binding_values(m111=m111_retenciones),
        relation_values=_RELATION_VALUES_2024,
        date_binding_values=_DATE_BINDINGS_2024,
    )

    assert result.values["0596"] == m111_retenciones, (
        f"casilla 0596 = {result.values['0596']!r}; expected {m111_retenciones!r} "
        f"from binding renta-2024-modelo-111-retenciones-periodicas. "
        "Check 2024/casillas/0578-0596.toml: must have "
        'input_kind = "bound" and binding = "renta-2024-modelo-111-retenciones-periodicas".'
    )


def test_m123_retenciones_flows_into_0609_total_pagos_a_cuenta(m100_2024_snapshot: RegistrySnapshot) -> None:
    """M123 retenciones in 0597 must propagate through 0609 to reduce cuota diferencial.

    The formula renta-2024-total-pagos-a-cuenta sums casillas 0592-0606 into
    0609.  With only M123 retenciones supplied, 0609 must equal the M123 amount.

    This exercises the full chain: binding → 0597 → formula → 0609.
    """
    m123_retenciones = Decimal("3800.00")
    result = calculate_registry_snapshot(
        m100_2024_snapshot,
        inputs={"0003": Decimal("0")},
        date_context=_DATE_CONTEXT_2024,
        enum_binding_values={"renta-2024-profile-tax-residence-ccaa": "madrid"},
        binding_values=_base_binding_values(m123=m123_retenciones),
        relation_values=_RELATION_VALUES_2024,
        date_binding_values=_DATE_BINDINGS_2024,
    )

    # 0609 = sum of all retenciones operands; only 0597 is non-zero here.
    assert result.values["0609"] == m123_retenciones, (
        f"casilla 0609 = {result.values['0609']!r}; expected {m123_retenciones!r}. "
        "With only renta-2024-modelo-123-retenciones-periodicas supplied "
        "and all other retenciones operands zero, "
        "0609 (total pagos a cuenta) must equal the M123 binding value."
    )


def test_zero_m123_retenciones_gives_zero_0597(m100_2024_snapshot: RegistrySnapshot) -> None:
    """Anti-tautology: with binding = 0, casilla 0597 must be 0 (not a stale value).

    This test would pass trivially if 0597 were always 0 (the pre-fix state).
    Combined with test_m123_retenciones_binding_populates_casilla_0597, the
    two tests together prove the channel is bidirectional and responsive.
    """
    result = calculate_registry_snapshot(
        m100_2024_snapshot,
        inputs={"0003": Decimal("0")},
        date_context=_DATE_CONTEXT_2024,
        enum_binding_values={"renta-2024-profile-tax-residence-ccaa": "madrid"},
        binding_values=_base_binding_values(m123=Decimal("0")),
        relation_values=_RELATION_VALUES_2024,
        date_binding_values=_DATE_BINDINGS_2024,
    )

    assert result.values["0597"] == Decimal("0"), (
        f"casilla 0597 = {result.values['0597']!r}; expected 0.00 when M123 binding is zero."
    )


def test_m123_retenciones_change_reflects_proportionally_in_0610(m100_2024_snapshot: RegistrySnapshot) -> None:
    """Changing M123 retenciones amount changes cuota diferencial by the same amount.

    Increases in M123 retenciones must reduce cuota diferencial (0610) by exactly
    the same delta. This guards against any intermediate transformation that would
    attenuate or amplify the value.
    """
    result_low = calculate_registry_snapshot(
        m100_2024_snapshot,
        inputs={"0003": Decimal("0")},
        date_context=_DATE_CONTEXT_2024,
        enum_binding_values={"renta-2024-profile-tax-residence-ccaa": "madrid"},
        binding_values=_base_binding_values(m123=Decimal("1000.00")),
        relation_values=_RELATION_VALUES_2024,
        date_binding_values=_DATE_BINDINGS_2024,
    )
    result_high = calculate_registry_snapshot(
        m100_2024_snapshot,
        inputs={"0003": Decimal("0")},
        date_context=_DATE_CONTEXT_2024,
        enum_binding_values={"renta-2024-profile-tax-residence-ccaa": "madrid"},
        binding_values=_base_binding_values(m123=Decimal("2000.00")),
        relation_values=_RELATION_VALUES_2024,
        date_binding_values=_DATE_BINDINGS_2024,
    )

    delta_0597 = result_high.values["0597"] - result_low.values["0597"]
    delta_0609 = result_high.values["0609"] - result_low.values["0609"]
    delta_0610 = result_low.values["0610"] - result_high.values["0610"]

    assert delta_0597 == Decimal("1000.00"), (
        f"expected 0597 to increase by 1000 when M123 binding increases by 1000, got delta={delta_0597!r}"
    )
    assert delta_0609 == Decimal("1000.00"), (
        f"0609 should increase by the same 1000 delta as 0597, got delta={delta_0609!r}"
    )
    assert delta_0610 == Decimal("1000.00"), (
        f"0610 (cuota diferencial) should decrease by 1000 when retenciones increase by 1000, got delta={delta_0610!r}"
    )
