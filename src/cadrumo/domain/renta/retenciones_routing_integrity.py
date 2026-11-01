"""Snapshot-time referential integrity for a registry-owned Renta route.

The route declaration is authored in the governed registry mapping. This
module retains only the generic query projection and the cross-domain check
that confirms a selected output endpoint exists before a consumer redirects a
resolved value to it.

The registry must not import the Renta domain directly. This module registers
the abstract snapshot check when the registry's snapshot builder imports the
declared module, preserving the dependency direction while keeping the check
at the domain boundary.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Final

from ...core.casilla_id import CasillaId, validated_casilla_id
from ...core.time.clock import today_madrid
from ..calculations.registry.binding_grade_cap_reach import register_binding_output_redirect
from ..calculations.registry.facts.resolution import MappingFactQuery, ResolvedMappingFact
from ..calculations.registry.governed_fact_scope import GovernedFactSource, require_governed_fact_authority
from ..calculations.registry.ids import BindingId
from ..calculations.registry.schema_base import DateAxis
from ..calculations.registry.validate_cross_domain_snapshot import register_cross_domain_snapshot_check

if TYPE_CHECKING:
    from ..calculations.registry.schema import ModeloRevision

M130_RETENCIONES_ROUTING_FACT_ID: Final = "m130-retenciones-output-routing"


@dataclass(frozen=True, slots=True)
class M130RetencionesRoute:
    """Generic typed projection of the selected registry route declaration."""

    modelo_id: str
    binding_id: BindingId
    output_casilla: CasillaId


# Registry authority: selected Renta binding routing is consumed through the governed mapping fact
def _registry_m130_retenciones_route(
    *,
    authority: GovernedFactSource | None = None,
) -> M130RetencionesRoute:
    """Resolve the selected route declaration without a Python fallback."""
    selected_authority = require_governed_fact_authority(authority, subject="Renta route")
    resolved = selected_authority.resolve_governed_fact(
        MappingFactQuery(
            fact_id=M130_RETENCIONES_ROUTING_FACT_ID,
            date_axis=DateAxis.FILING_PERIOD,
            effective_date=today_madrid(),
        ),
    )
    if not isinstance(resolved, ResolvedMappingFact):
        raise TypeError("Renta route must resolve as a mapping fact")
    entries: dict[str, str] = {}
    for entry in resolved.payload.entries:
        if not isinstance(entry.key, str) or not isinstance(entry.value, str):
            raise TypeError("Renta route entries must be string-to-string")
        if entry.key in entries:
            raise ValueError(f"duplicate Renta route key {entry.key!r}")
        entries[entry.key] = entry.value.strip()

    def required(key: str) -> str:
        value = entries.get(key)
        if value is None or not value:
            raise ValueError(f"Renta route is missing {key!r}")
        return value

    return M130RetencionesRoute(
        modelo_id=required("modelo"),
        binding_id=required("binding_id"),
        output_casilla=validated_casilla_id(
            required("output_casilla"),
            surface="registry_renta_retenciones_route",
        ),
    )


def resolve_m130_retenciones_route(*, authority: GovernedFactSource | None = None) -> M130RetencionesRoute:
    """Return the selected route for application-layer binding projection."""
    return _registry_m130_retenciones_route(authority=authority)


def check_m130_retenciones_output_casilla(
    modelo_id: str,
    casilla_ids: frozenset[CasillaId],
    renta_first_slice_binding_targets: frozenset[CasillaId],  # shared Protocol shape, unused here
    revision_binding_ids: frozenset[BindingId] = frozenset(),
    *,
    filing_year: int,
) -> list[str]:
    """Assert a selected route output endpoint exists when its binding is declared."""
    del filing_year
    route = _registry_m130_retenciones_route()
    if modelo_id != route.modelo_id:
        return []
    if route.binding_id not in revision_binding_ids:
        return []
    if route.output_casilla in casilla_ids:
        return []
    return [
        f"selected revision declares binding {route.binding_id!r} but its "
        f"retenciones output casilla {route.output_casilla!r} "
        "is absent from the revision -- the resolved retencion would be written nowhere "
        "the filed form reads",
    ]


def m130_retenciones_output_redirect(
    revision: ModeloRevision, authority: GovernedFactSource | None
) -> dict[BindingId, tuple[CasillaId, ...]]:
    """Return the routed binding of ``revision`` and the output casilla the route writes it to.

    Empty unless the revision declares both the routed binding and its output
    casilla: a revision without the binding has nothing redirected, and one
    without the casilla is refused by the snapshot check above.
    """
    route = _registry_m130_retenciones_route(authority=authority)
    if route.binding_id not in {binding.id for binding in revision.bindings}:
        return {}
    if route.output_casilla not in {casilla.id for casilla in revision.casillas}:
        return {}
    return {route.binding_id: (route.output_casilla,)}


register_cross_domain_snapshot_check(check_m130_retenciones_output_casilla)
register_binding_output_redirect(m130_retenciones_output_redirect)


__all__ = [
    "M130_RETENCIONES_ROUTING_FACT_ID",
    "M130RetencionesRoute",
    "check_m130_retenciones_output_casilla",
    "m130_retenciones_output_redirect",
    "resolve_m130_retenciones_route",
]
