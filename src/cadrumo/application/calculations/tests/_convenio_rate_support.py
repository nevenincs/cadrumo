"""Shared Modelo 210 convenio (double-taxation treaty) rate resolution for tests."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from ....core import validated_casilla_id
from ....domain.calculations.registry.authority import bundled_authority
from ....domain.calculations.registry.bindings import resolve_available_bound_inputs_by_casilla_id
from ....domain.calculations.registry.formula_runtime import calculate_registry_snapshot
from ....domain.calculations.registry.ids import BindingId

_MODELO = "210"
_YEAR = 2025
_COUNTRY_BINDING = "m210-2025-profile-country-of-fiscal-residence"
_SURFACE = "convenio_rate_test"
_TIPO_GRAVAMEN = validated_casilla_id("tipo_gravamen", surface=_SURFACE)
_CUOTA_INTEGRA = validated_casilla_id("cuota_integra", surface=_SURFACE)


def resolve_convenio_rate(*, tipo_renta: str, country_code: str, base: str) -> tuple[Decimal, Decimal]:
    """Drive the REAL M210 engine and return (tipo_gravamen, cuota_integra).

    The treaty override (ceiling, exemption, or flat) is resolved entirely by
    the registry engine from ``country_code`` and ``tipo_renta`` — this helper
    hardcodes no per-country rate or treaty-specific branching. Every caller
    supplies its own grounded rate and legal citation for its own assertions.
    """
    snapshot = bundled_authority().snapshot(_MODELO, filing_year=_YEAR, period="EVENT-1")
    binding_values: dict[BindingId, Decimal] = {}
    enum_binding_values: dict[BindingId, str] = {_COUNTRY_BINDING: country_code}
    text_inputs = {validated_casilla_id("tipo_renta", surface=_SURFACE): tipo_renta}
    casilla_inputs = {
        validated_casilla_id("rendimientos_integros", surface=_SURFACE): Decimal(base),
        validated_casilla_id("gastos_deducibles", surface=_SURFACE): Decimal("0"),
        validated_casilla_id("retencion_practicada", surface=_SURFACE): Decimal("0"),
    }
    bound = resolve_available_bound_inputs_by_casilla_id(snapshot.revision, binding_values)
    result = calculate_registry_snapshot(
        snapshot,
        inputs={**bound, **casilla_inputs},
        binding_values=binding_values,
        enum_binding_values=enum_binding_values,
        text_inputs=text_inputs,
        date_context={"filing_period": date(_YEAR, 12, 31)},
    )
    return result.values[_TIPO_GRAVAMEN], result.values[_CUOTA_INTEGRA]
