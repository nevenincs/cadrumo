"""Calculate a Modelo 100 return whose pension-system inputs are named by semantic role.

The pension-system reduction (LIRPF art. 52) is exercised by registry tests and by the
application's advisory tests through the same real resolver; both state their inputs by role,
never by box number, so this helper resolves each role in the revision it is given.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date
from decimal import Decimal

from .....core.aggregation import BindingSourceKind
from ..bindings import resolve_available_bound_inputs_by_casilla_id
from ..formula_runtime import RegistryCalculationResult, calculate_registry_snapshot
from ..renta_inmueble_bindings import renta_inmueble_totals
from ..schema import RegistrySnapshot
from .modelo_100_registry_support import neutral_binding_values

__all__ = ["ROLE_ALQUILER", "calculate_m100_by_role", "casilla_for_role"]

_FAMILIES = ("capital-mobiliario", "capital-inmobiliario", "ganancias-patrimoniales")
_EXCLUDED_BINDING = "renta-profile-income-family-excluded-"
_DECLARATION_TYPE = "renta-profile-declaration-type"

#: The let properties' reduced net yield, the rental income the general base reads.
ROLE_ALQUILER = "irpf_rendimiento_capital_inmobiliario_rendimiento_neto_reducido"
#: The 60.000 box of art. 52.1.b.1.º: it marks income up to 60.000 until the official design
#: turned it round to mark income above 60.000.
_ROLE_FLAG_UP_TO_60000 = "irpf_red_prevision_social_rendimientos_trabajo_igual_inferior_60000_flag"
_ROLE_FLAG_ABOVE_60000 = "irpf_red_prevision_social_rendimientos_trabajo_superior_60000_flag"


def casilla_for_role(snapshot: RegistrySnapshot, role: str) -> str:
    """Return the one casilla of the snapshot's revision that bears ``role``."""
    matches = [str(casilla.id) for casilla in snapshot.revision.casillas if casilla.semantic_role == role]
    assert len(matches) == 1, (role, matches)
    return matches[0]


def _has_role(snapshot: RegistrySnapshot, role: str) -> bool:
    return any(casilla.semantic_role == role for casilla in snapshot.revision.casillas)


def _route_figures(
    snapshot: RegistrySnapshot, figures: Mapping[str, Decimal], decimals: dict[str, Decimal]
) -> dict[str, Decimal]:
    """Put each figure where the revision reads it: its binding, its let-property column total, or its box."""
    column_totals = {
        str(provider.target_casilla_id): binding.id for binding, provider in renta_inmueble_totals(snapshot.revision)
    }
    inputs: dict[str, Decimal] = {}
    for role, value in figures.items():
        casilla = next(item for item in snapshot.revision.casillas if item.semantic_role == role)
        if casilla.binding is not None:
            decimals[casilla.binding] = value
        elif str(casilla.id) in column_totals:
            # A let property's column is held per row; the calculation reads its total over the rows.
            decimals[column_totals[str(casilla.id)]] = value
        else:
            inputs[str(casilla.id)] = value
    return inputs


def _income_flags(snapshot: RegistrySnapshot, *, income_up_to_60000: bool) -> dict[str, Decimal]:
    flags: dict[str, Decimal] = {}
    if _has_role(snapshot, _ROLE_FLAG_UP_TO_60000):
        flags[casilla_for_role(snapshot, _ROLE_FLAG_UP_TO_60000)] = Decimal(1 if income_up_to_60000 else 0)
    if _has_role(snapshot, _ROLE_FLAG_ABOVE_60000):
        flags[casilla_for_role(snapshot, _ROLE_FLAG_ABOVE_60000)] = Decimal(0 if income_up_to_60000 else 1)
    return flags


def calculate_m100_by_role(
    snapshot: RegistrySnapshot,
    year: int,
    figures: Mapping[str, Decimal],
    *,
    declaration_type: int = 1,
    income_up_to_60000: bool = True,
) -> RegistryCalculationResult:
    """Calculate one return whose inputs are named by role; the profile states rental income only when given."""
    bindings = tuple(
        binding for binding in snapshot.revision.bindings if binding.source is not BindingSourceKind.RELATION_PREFILL
    )
    decimals, booleans, dates, enums = neutral_binding_values(bindings)
    booleans["renta-modelo-100-estimacion-directa-es-normal"] = True
    decimals |= {_DECLARATION_TYPE: Decimal(declaration_type)}
    has_rent = ROLE_ALQUILER in figures
    for family in _FAMILIES:
        booleans[_EXCLUDED_BINDING + family] = not (family == "capital-inmobiliario" and has_rent)
    inputs = _route_figures(snapshot, figures, decimals) | _income_flags(
        snapshot, income_up_to_60000=income_up_to_60000
    )
    return calculate_registry_snapshot(
        snapshot,
        inputs={**inputs, **resolve_available_bound_inputs_by_casilla_id(snapshot.revision, decimals)},
        date_context={"filing_period": date(year, 12, 31)},
        binding_values=decimals,
        enum_binding_values=enums,
        relation_values={
            "renta-modelo-130-pagos-fraccionados": Decimal(0),
            "renta-modelo-131-pagos-fraccionados": Decimal(0),
        },
        date_binding_values=dates,
        boolean_binding_values=booleans,
    )
