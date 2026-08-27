"""Regression guard: M111 → casilla 0596 and M123 → casilla 0597 binding wiring.

Before this fix, casillas 0596 and 0597 in the 2024 revision had no
``input_kind = "bound"`` and no ``binding`` field, so
``resolve_available_bound_inputs_by_casilla_id`` silently skipped them.
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

from .....core import CasillaId, validated_casilla_id
from ..errors import RegistryValidationError
from ..formula_runtime import calculate_registry_snapshot
from ..ids import BindingId, RelationId
from ..schema import RegistrySnapshot
from ._modelo_100_registry_support import _m100_2024_deduccion_maternidad_bindings

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_M100_MINIMO_PERSONAL_CASILLA: CasillaId = validated_casilla_id("0003", surface="_M100_MINIMO_PERSONAL_CASILLA")
_M100_RETENCIONES_M111_CASILLA: CasillaId = validated_casilla_id("0596", surface="_M100_RETENCIONES_M111_CASILLA")
_M100_RETENCIONES_M123_CASILLA: CasillaId = validated_casilla_id("0597", surface="_M100_RETENCIONES_M123_CASILLA")
_M100_TOTAL_PAGOS_A_CUENTA_CASILLA: CasillaId = validated_casilla_id(
    "0609",
    surface="_M100_TOTAL_PAGOS_A_CUENTA_CASILLA",
)
_M100_CUOTA_DIFERENCIAL_CASILLA: CasillaId = validated_casilla_id("0610", surface="_M100_CUOTA_DIFERENCIAL_CASILLA")

_DATE_CONTEXT_2024 = {"filing_period": date(2024, 12, 31)}
_DATE_BINDINGS_2024: dict[BindingId, date] = {"renta-2024-profile-taxpayer-birth-date": date(1975, 6, 15)}
_DATE_CONTEXT_2025 = {"filing_period": date(2025, 12, 31)}
_DATE_BINDINGS_2025: dict[BindingId, date] = {"renta-2025-profile-taxpayer-birth-date": date(1975, 6, 15)}

_RELATION_VALUES_2024: dict[RelationId, Decimal] = {
    "renta-2024-rel-111-retenciones-trimestrales": Decimal("0"),
    "renta-2024-rel-111-retenciones-mensuales": Decimal("0"),
    "renta-2024-rel-123-retenciones-trimestrales": Decimal("0"),
    "renta-2024-rel-193-retenciones-anuales": Decimal("0"),
    "renta-2024-rel-130-pagos-fraccionados": Decimal("0"),
    "renta-2024-rel-131-pagos-fraccionados": Decimal("0"),
}
_RELATION_VALUES_2025: dict[RelationId, Decimal] = {
    "renta-2025-rel-130-pagos-fraccionados": Decimal("0"),
    "renta-2025-rel-131-pagos-fraccionados": Decimal("0"),
}


def _base_binding_values(
    *,
    m111: Decimal | None = None,
    certificado_trabajo: Decimal | None = None,
    m123: Decimal | None = None,
    m193: Decimal | None = None,
) -> dict[BindingId, Decimal]:
    values: dict[BindingId, Decimal] = {
        "renta-2024-modelo-100-estimacion-directa-es-normal": Decimal("1"),
        "renta-2024-profile-declaration-type": Decimal("1"),
        "renta-2024-profile-family-minor-children-in-unit": Decimal("0"),
        # Art. 81.1 LIRPF maternity deduction: zero in these retenciones scenarios,
        # which declare no qualifying descendant.
        **_m100_2024_deduccion_maternidad_bindings(),
        # Art. 81.2 LIRPF guarderia bindings (b7ad3a993): zero in non-guarderia scenarios.
        "renta-2024-profile-guarderia-gastos-reales": Decimal("0"),
        "renta-2024-profile-incremento-guarderia": Decimal("0"),
        "renta-2024-profile-cotizaciones-ss-madre": Decimal("0"),
        "renta-2024-profile-descendientes-guarderia": Decimal("0"),
        "renta-2024-profile-minimo-descendientes-estatal": Decimal("0"),
        "renta-2024-profile-minimo-descendientes-autonomico": Decimal("0"),
        "renta-2024-profile-marriage-full-year": Decimal("0"),
        "renta-2024-profile-marriage-month-start": Decimal("0"),
        "renta-2024-profile-marriage-month-end": Decimal("0"),
        # BIN-pendiente fresh-filer baseline.
        "renta-2024-base-liquidable-negativa-general-anterior": Decimal("0"),
    }
    if m111 is not None:
        values["renta-2024-modelo-111-retenciones-periodicas"] = m111
    if certificado_trabajo is not None:
        values["renta-2024-certificado-trabajo-retenciones"] = certificado_trabajo
    if m123 is not None:
        values["renta-2024-modelo-123-retenciones-periodicas"] = m123
    if m193 is not None:
        values["renta-2024-modelo-193-retenciones-anuales"] = m193
    return values


def _base_binding_values_2025(
    *,
    m111: Decimal | None = None,
    m190: Decimal | None = None,
    certificado_trabajo: Decimal | None = None,
    m123: Decimal | None = None,
    m193: Decimal | None = None,
) -> dict[BindingId, Decimal]:
    values: dict[BindingId, Decimal] = {
        # The production profile resolver supplies this predicate as 1/0 from
        # taxpayer_type.irpf_income_categories; the scenario models a directa filer.
        "renta-2025-profile-has-economic-activity": Decimal("1"),
        "renta-2025-modelo-100-estimacion-directa-es-normal": Decimal("1"),
        "renta-2025-modelo-184-atribucion-actividades-economicas": Decimal("0"),
        "renta-2025-profile-declaration-type": Decimal("1"),
        "renta-2025-profile-family-minor-children-in-unit": Decimal("0"),
        "renta-2025-profile-marriage-full-year": Decimal("0"),
        "renta-2025-profile-marriage-month-start": Decimal("0"),
        "renta-2025-profile-marriage-month-end": Decimal("0"),
        "renta-2025-base-liquidable-negativa-general-anterior": Decimal("0"),
        "renta-2025-profile-minimo-descendientes-estatal": Decimal("0"),
        "renta-2025-profile-minimo-descendientes-autonomico": Decimal("0"),
    }
    if m111 is not None:
        values["renta-2025-modelo-111-retenciones-periodicas"] = m111
    if m190 is not None:
        values["renta-2025-modelo-190-retenciones-anuales"] = m190
    if certificado_trabajo is not None:
        values["renta-2025-certificado-trabajo-retenciones"] = certificado_trabajo
    if m123 is not None:
        values["renta-2025-modelo-123-retenciones-periodicas"] = m123
    if m193 is not None:
        values["renta-2025-modelo-193-retenciones-anuales"] = m193
    return values


def test_m190_annual_retenciones_binding_populates_2025_casilla_0596(
    m100_2025_snapshot: RegistrySnapshot,
) -> None:
    """M190 annual retenciones are a reviewed equivalent source for M100/2025 0596.

    Regression guard: a previously reported defect had the binding accepted but left 0596 at zero.
    This exercises binding projection and formula propagation, not a duplicated
    rental or salary arithmetic oracle.
    """
    annual_retenciones = Decimal("4200.00")

    result = calculate_registry_snapshot(
        m100_2025_snapshot,
        inputs={"0003": Decimal("32000"), "0102": Decimal("9600")},
        date_context=_DATE_CONTEXT_2025,
        enum_binding_values={"renta-2025-profile-tax-residence-ccaa": "madrid"},
        binding_values=_base_binding_values_2025(m190=annual_retenciones),
        relation_values=_RELATION_VALUES_2025,
        date_binding_values=_DATE_BINDINGS_2025,
    )

    assert result.values[_M100_RETENCIONES_M111_CASILLA] == annual_retenciones, (
        f"casilla 0596 = {result.values[_M100_RETENCIONES_M111_CASILLA]!r}; expected {annual_retenciones!r} "
        "from equivalent binding renta-2025-modelo-190-retenciones-anuales."
    )
    assert result.values[_M100_TOTAL_PAGOS_A_CUENTA_CASILLA] == annual_retenciones, (
        "0609 must include the M190-sourced work-retention credit instead of "
        f"silently treating 0596 as zero; got {result.values[_M100_TOTAL_PAGOS_A_CUENTA_CASILLA]!r}."
    )
    observation = next(obs for obs in result.observations if obs.casilla_id == _M100_RETENCIONES_M111_CASILLA)
    assert not observation.absent_by_design
    assert "boe-modelo-190-2025-form" in observation.source_refs


def test_salary_certificate_retenciones_binding_populates_2024_casilla_0596(
    m100_2024_snapshot: RegistrySnapshot,
) -> None:
    """Payee salary-certificate withholding is a public M100/2024 source for 0596."""
    suffered_retenciones = Decimal("4500.00")

    result = calculate_registry_snapshot(
        m100_2024_snapshot,
        inputs={_M100_MINIMO_PERSONAL_CASILLA: Decimal("30000.00")},
        date_context=_DATE_CONTEXT_2024,
        enum_binding_values={"renta-2024-profile-tax-residence-ccaa": "madrid"},
        binding_values=_base_binding_values(certificado_trabajo=suffered_retenciones),
        relation_values=_RELATION_VALUES_2024,
        date_binding_values=_DATE_BINDINGS_2024,
    )

    assert result.values[_M100_RETENCIONES_M111_CASILLA] == suffered_retenciones
    assert result.values[_M100_TOTAL_PAGOS_A_CUENTA_CASILLA] == suffered_retenciones
    observation = next(obs for obs in result.observations if obs.casilla_id == _M100_RETENCIONES_M111_CASILLA)
    assert not observation.absent_by_design
    assert "aeat-renta-2024-manual-parte1" in observation.source_refs


def test_conflicting_2024_m111_and_salary_certificate_retenciones_refuse_before_calculation(
    m100_2024_snapshot: RegistrySnapshot,
) -> None:
    """Filed/payer relation evidence and payee certificate input must agree exactly."""
    with pytest.raises(RegistryValidationError, match="conflicting equivalent binding values"):
        calculate_registry_snapshot(
            m100_2024_snapshot,
            inputs={_M100_MINIMO_PERSONAL_CASILLA: Decimal("30000.00")},
            date_context=_DATE_CONTEXT_2024,
            enum_binding_values={"renta-2024-profile-tax-residence-ccaa": "madrid"},
            binding_values=_base_binding_values(
                m111=Decimal("4500.00"),
                certificado_trabajo=Decimal("4499.99"),
            ),
            relation_values=_RELATION_VALUES_2024,
            date_binding_values=_DATE_BINDINGS_2024,
        )


def test_salary_certificate_retenciones_binding_populates_2025_casilla_0596(
    m100_2025_snapshot: RegistrySnapshot,
) -> None:
    """2025 keeps parity for the payee salary-certificate withholding input."""
    suffered_retenciones = Decimal("4500.00")

    result = calculate_registry_snapshot(
        m100_2025_snapshot,
        inputs={"0003": Decimal("30000.00"), "0102": Decimal("9600")},
        date_context=_DATE_CONTEXT_2025,
        enum_binding_values={"renta-2025-profile-tax-residence-ccaa": "madrid"},
        binding_values=_base_binding_values_2025(certificado_trabajo=suffered_retenciones),
        relation_values=_RELATION_VALUES_2025,
        date_binding_values=_DATE_BINDINGS_2025,
    )

    assert result.values[_M100_RETENCIONES_M111_CASILLA] == suffered_retenciones
    assert result.values[_M100_TOTAL_PAGOS_A_CUENTA_CASILLA] == suffered_retenciones


def test_conflicting_2025_m111_and_m190_retenciones_refuse_before_calculation(
    m100_2025_snapshot: RegistrySnapshot,
) -> None:
    """Equivalent M111/M190 sources must agree exactly or calculation refuses."""
    with pytest.raises(RegistryValidationError, match="conflicting equivalent binding values"):
        calculate_registry_snapshot(
            m100_2025_snapshot,
            inputs={"0003": Decimal("32000"), "0102": Decimal("9600")},
            date_context=_DATE_CONTEXT_2025,
            enum_binding_values={"renta-2025-profile-tax-residence-ccaa": "madrid"},
            binding_values=_base_binding_values_2025(m111=Decimal("4200.00"), m190=Decimal("4100.00")),
            relation_values=_RELATION_VALUES_2025,
            date_binding_values=_DATE_BINDINGS_2025,
        )


def test_m193_annual_retenciones_binding_populates_2025_casilla_0597(
    m100_2025_snapshot: RegistrySnapshot,
) -> None:
    """M193 annual capital-mobiliario retentions are equivalent source evidence for 0597."""
    annual_retenciones = Decimal("975.31")

    result = calculate_registry_snapshot(
        m100_2025_snapshot,
        inputs={"0003": Decimal("32000"), "0102": Decimal("9600")},
        date_context=_DATE_CONTEXT_2025,
        enum_binding_values={"renta-2025-profile-tax-residence-ccaa": "madrid"},
        binding_values=_base_binding_values_2025(m193=annual_retenciones),
        relation_values=_RELATION_VALUES_2025,
        date_binding_values=_DATE_BINDINGS_2025,
    )

    assert result.values[_M100_RETENCIONES_M123_CASILLA] == annual_retenciones, (
        f"casilla 0597 = {result.values[_M100_RETENCIONES_M123_CASILLA]!r}; expected {annual_retenciones!r} "
        "from equivalent binding renta-2025-modelo-193-retenciones-anuales."
    )
    assert result.values[_M100_TOTAL_PAGOS_A_CUENTA_CASILLA] == annual_retenciones
    observation = next(obs for obs in result.observations if obs.casilla_id == _M100_RETENCIONES_M123_CASILLA)
    assert "boe-modelo-193-2011-form" in observation.source_refs


def test_conflicting_2025_m123_and_m193_retenciones_refuse_before_calculation(
    m100_2025_snapshot: RegistrySnapshot,
) -> None:
    """Equivalent M123/M193 capital-mobiliario sources must agree exactly."""
    with pytest.raises(RegistryValidationError, match="conflicting equivalent binding values"):
        calculate_registry_snapshot(
            m100_2025_snapshot,
            inputs={"0003": Decimal("32000"), "0102": Decimal("9600")},
            date_context=_DATE_CONTEXT_2025,
            enum_binding_values={"renta-2025-profile-tax-residence-ccaa": "madrid"},
            binding_values=_base_binding_values_2025(m123=Decimal("975.31"), m193=Decimal("975.30")),
            relation_values=_RELATION_VALUES_2025,
            date_binding_values=_DATE_BINDINGS_2025,
        )


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
        inputs={_M100_MINIMO_PERSONAL_CASILLA: Decimal("0")},
        date_context=_DATE_CONTEXT_2024,
        enum_binding_values={"renta-2024-profile-tax-residence-ccaa": "madrid"},
        binding_values=_base_binding_values(m123=m123_retenciones),
        relation_values=_RELATION_VALUES_2024,
        date_binding_values=_DATE_BINDINGS_2024,
    )

    assert result.values[_M100_RETENCIONES_M123_CASILLA] == m123_retenciones, (
        f"casilla 0597 = {result.values[_M100_RETENCIONES_M123_CASILLA]!r}; expected {m123_retenciones!r} "
        f"from binding renta-2024-modelo-123-retenciones-periodicas. "
        "Check 2024/casillas/c0597.toml: must have "
        'input_kind = "bound" and binding = "renta-2024-modelo-123-retenciones-periodicas".'
    )


def test_m193_annual_retenciones_binding_populates_2024_casilla_0597(
    m100_2024_snapshot: RegistrySnapshot,
) -> None:
    """M193 annual capital-mobiliario retentions must not be silently dropped in 2024."""
    annual_retenciones = Decimal("864.20")
    result = calculate_registry_snapshot(
        m100_2024_snapshot,
        inputs={_M100_MINIMO_PERSONAL_CASILLA: Decimal("0")},
        date_context=_DATE_CONTEXT_2024,
        enum_binding_values={"renta-2024-profile-tax-residence-ccaa": "madrid"},
        binding_values=_base_binding_values(m193=annual_retenciones),
        relation_values=_RELATION_VALUES_2024,
        date_binding_values=_DATE_BINDINGS_2024,
    )

    assert result.values[_M100_RETENCIONES_M123_CASILLA] == annual_retenciones, (
        f"casilla 0597 = {result.values[_M100_RETENCIONES_M123_CASILLA]!r}; expected {annual_retenciones!r} "
        "from equivalent binding renta-2024-modelo-193-retenciones-anuales."
    )
    assert result.values[_M100_TOTAL_PAGOS_A_CUENTA_CASILLA] == annual_retenciones
    observation = next(obs for obs in result.observations if obs.casilla_id == _M100_RETENCIONES_M123_CASILLA)
    assert "boe-modelo-193-2011-form" in observation.source_refs


def test_conflicting_2024_m123_and_m193_retenciones_refuse_before_calculation(
    m100_2024_snapshot: RegistrySnapshot,
) -> None:
    """Equivalent M123/M193 capital-mobiliario sources must agree exactly."""
    with pytest.raises(RegistryValidationError, match="conflicting equivalent binding values"):
        calculate_registry_snapshot(
            m100_2024_snapshot,
            inputs={_M100_MINIMO_PERSONAL_CASILLA: Decimal("0")},
            date_context=_DATE_CONTEXT_2024,
            enum_binding_values={"renta-2024-profile-tax-residence-ccaa": "madrid"},
            binding_values=_base_binding_values(m123=Decimal("864.20"), m193=Decimal("864.21")),
            relation_values=_RELATION_VALUES_2024,
            date_binding_values=_DATE_BINDINGS_2024,
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
        inputs={_M100_MINIMO_PERSONAL_CASILLA: Decimal("0")},
        date_context=_DATE_CONTEXT_2024,
        enum_binding_values={"renta-2024-profile-tax-residence-ccaa": "madrid"},
        binding_values=_base_binding_values(m111=m111_retenciones),
        relation_values=_RELATION_VALUES_2024,
        date_binding_values=_DATE_BINDINGS_2024,
    )

    assert result.values[_M100_RETENCIONES_M111_CASILLA] == m111_retenciones, (
        f"casilla 0596 = {result.values[_M100_RETENCIONES_M111_CASILLA]!r}; expected {m111_retenciones!r} "
        f"from binding renta-2024-modelo-111-retenciones-periodicas. "
        "Check 2024/casillas/c0596.toml: must have "
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
        inputs={_M100_MINIMO_PERSONAL_CASILLA: Decimal("0")},
        date_context=_DATE_CONTEXT_2024,
        enum_binding_values={"renta-2024-profile-tax-residence-ccaa": "madrid"},
        binding_values=_base_binding_values(m123=m123_retenciones),
        relation_values=_RELATION_VALUES_2024,
        date_binding_values=_DATE_BINDINGS_2024,
    )

    # 0609 = sum of all retenciones operands; only 0597 is non-zero here.
    assert result.values[_M100_TOTAL_PAGOS_A_CUENTA_CASILLA] == m123_retenciones, (
        f"casilla 0609 = {result.values[_M100_TOTAL_PAGOS_A_CUENTA_CASILLA]!r}; expected {m123_retenciones!r}. "
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
        inputs={_M100_MINIMO_PERSONAL_CASILLA: Decimal("0")},
        date_context=_DATE_CONTEXT_2024,
        enum_binding_values={"renta-2024-profile-tax-residence-ccaa": "madrid"},
        binding_values=_base_binding_values(m123=Decimal("0")),
        relation_values=_RELATION_VALUES_2024,
        date_binding_values=_DATE_BINDINGS_2024,
    )

    assert result.values[_M100_RETENCIONES_M123_CASILLA] == Decimal("0"), (
        f"casilla 0597 = {result.values[_M100_RETENCIONES_M123_CASILLA]!r}; expected 0.00 when M123 binding is zero."
    )


def test_m123_retenciones_change_reflects_proportionally_in_0610(m100_2024_snapshot: RegistrySnapshot) -> None:
    """Changing M123 retenciones amount changes cuota diferencial by the same amount.

    Increases in M123 retenciones must reduce cuota diferencial (0610) by exactly
    the same delta. This guards against any intermediate transformation that would
    attenuate or amplify the value.
    """
    result_low = calculate_registry_snapshot(
        m100_2024_snapshot,
        inputs={_M100_MINIMO_PERSONAL_CASILLA: Decimal("0")},
        date_context=_DATE_CONTEXT_2024,
        enum_binding_values={"renta-2024-profile-tax-residence-ccaa": "madrid"},
        binding_values=_base_binding_values(m123=Decimal("1000.00")),
        relation_values=_RELATION_VALUES_2024,
        date_binding_values=_DATE_BINDINGS_2024,
    )
    result_high = calculate_registry_snapshot(
        m100_2024_snapshot,
        inputs={_M100_MINIMO_PERSONAL_CASILLA: Decimal("0")},
        date_context=_DATE_CONTEXT_2024,
        enum_binding_values={"renta-2024-profile-tax-residence-ccaa": "madrid"},
        binding_values=_base_binding_values(m123=Decimal("2000.00")),
        relation_values=_RELATION_VALUES_2024,
        date_binding_values=_DATE_BINDINGS_2024,
    )

    delta_0597 = result_high.values[_M100_RETENCIONES_M123_CASILLA] - result_low.values[_M100_RETENCIONES_M123_CASILLA]
    delta_0609 = (
        result_high.values[_M100_TOTAL_PAGOS_A_CUENTA_CASILLA] - result_low.values[_M100_TOTAL_PAGOS_A_CUENTA_CASILLA]
    )
    delta_0610 = (
        result_low.values[_M100_CUOTA_DIFERENCIAL_CASILLA] - result_high.values[_M100_CUOTA_DIFERENCIAL_CASILLA]
    )

    assert delta_0597 == Decimal("1000.00"), (
        f"expected 0597 to increase by 1000 when M123 binding increases by 1000, got delta={delta_0597!r}"
    )
    assert delta_0609 == Decimal("1000.00"), (
        f"0609 should increase by the same 1000 delta as 0597, got delta={delta_0609!r}"
    )
    assert delta_0610 == Decimal("1000.00"), (
        f"0610 (cuota diferencial) should decrease by 1000 when retenciones increase by 1000, got delta={delta_0610!r}"
    )
