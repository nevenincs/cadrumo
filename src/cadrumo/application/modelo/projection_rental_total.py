"""The property totals the Modelo 100 projection reads.

The projection estimates the year from the Modelo 130 activity income, but the
art. 20 limit also weighs the net yield of every let property, and the general
base (casilla 0155) adds the art. 85 income imputed for every property at its
owner's disposal (casilla 0089). Both totals come from the same
``renta_inmueble`` resolver the annual calculation uses, so a property with net
rent or imputed income counts in the estimate, a filer whose stated properties
carry none states a proven 0.00, and a property whose figure is unknown (or a
profile that cannot be read) leaves the total unresolved instead of reading as
zero.
"""

from __future__ import annotations

from ...domain.calculations.registry.renta_inmueble_bindings import renta_inmueble_totals
from ..aggregation.renta_inmueble_resolver import RentaInmuebleSourceResolver
from ..aggregation.renta_inmueble_source import RentaInmuebleRowField
from ..aggregation.source_mesh import CalculationSourceContext, CalculationSourceResolution
from .calculation_action_ports import CalculationActionPorts
from .calculation_route import require_calculation_route_resolver

_PROJECTED_TOTAL_FIELDS = frozenset(
    {RentaInmuebleRowField.RENDIMIENTO_NETO.value, RentaInmuebleRowField.RENTA_IMPUTADA.value}
)


def rental_total_resolution(
    context: CalculationSourceContext, *, ports: CalculationActionPorts
) -> CalculationSourceResolution | None:
    """Resolve the net-yield and imputed-income totals the projection's formulas read.

    Returns ``None`` when the revision declares neither total. Only those totals
    are taken: the projection reads no property rows, so the other column totals stay
    as they were. The per-property rows are dropped, and the findings the resolver
    raised stay as diagnostics beside the total.
    """
    total_ids = {
        binding.id
        for binding, provider in renta_inmueble_totals(context.revision)
        if provider.row_field in _PROJECTED_TOTAL_FIELDS
    }
    if not total_ids:
        return None
    resolver = RentaInmuebleSourceResolver(
        transaction_repository=ports.transaction_repository,
        retencion_soportada_ports=ports.retencion_soportada_ports,
    )
    require_calculation_route_resolver("mesh", resolver)
    resolution = resolver.resolve(context)
    return CalculationSourceResolution(
        resolver_id=resolution.resolver_id,
        owned_sources=resolution.owned_sources,
        binding_values={key: value for key, value in resolution.binding_values.items() if key in total_ids},
        unresolved_binding_ids=tuple(key for key in resolution.unresolved_binding_ids if key in total_ids),
        diagnostics=resolution.diagnostics,
        provenance=resolution.provenance,
    )
