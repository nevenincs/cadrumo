"""The dated declaration of how the quarterly Modelo 130 figures reach the annual Modelo 100.

The registry declares, per filing year, which quarterly declaration feeds which
annual return, in which revision of it, and which box carries each figure. The
projection reads the declaration here, and the work form asks the same
:func:`modelo_projection_available` for its ``projectable`` capability, so the
operation and the capability can never disagree about a year.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import TYPE_CHECKING

from ...core.casilla_id import CasillaId, validated_casilla_id
from ...core.period import Period
from ...domain.calculations.registry.errors import GovernedFactNotApplicableError, RegistryValidationError
from ...domain.calculations.registry.facts.resolution import MappingFactQuery, ResolvedMappingFact
from ...domain.calculations.registry.schema_base import DateAxis
from .registry_input_refusals import registry_integrity_verdict

if TYPE_CHECKING:
    from ...domain.calculations.registry.authority import PinnedAuthorityOperation


@dataclass(frozen=True, slots=True)
class ProjectionDeclaration:
    """The modelos, period and boxes the dated cross-model projection fact declares."""

    source_modelo: str
    target_modelo: str
    target_period: str
    target_revision: str
    ingresos: CasillaId
    gastos: CasillaId
    rendimiento_neto: CasillaId
    resultado_final: CasillaId
    rendimiento_neto_projected: CasillaId
    base_liquidable_general: CasillaId
    cuota_integra_estatal: CasillaId
    cuota_integra_autonomica: CasillaId
    cuota_liquida_estatal: CasillaId
    cuota_liquida_autonomica: CasillaId
    cuota_resultante: CasillaId
    pagos_fraccionados: CasillaId


def registry_projection_declaration(year: int, *, operation: PinnedAuthorityOperation) -> ProjectionDeclaration:
    """Resolve the dated cross-model projection declaration from the registry."""
    resolved = operation.resolve_governed_fact(
        MappingFactQuery(
            fact_id="modelo-100-m130-projection-mapping",
            date_axis=DateAxis.FILING_PERIOD,
            effective_date=date(year, 12, 31),
        ),
    )
    if not isinstance(resolved, ResolvedMappingFact):
        raise TypeError("selected projection declaration must resolve as a mapping fact")
    return projection_declaration_from(resolved)


def projection_declaration_from(resolved: ResolvedMappingFact) -> ProjectionDeclaration:
    """Read the declared entries, refusing a mapping that omits one."""
    entries = {entry.key: str(entry.value) for entry in resolved.payload.entries}

    def declared(key: str) -> str:
        try:
            return entries[key]
        except KeyError as exc:
            raise RegistryValidationError(
                f"projection mapping is missing {key!r}",
                precondition_verdict=registry_integrity_verdict("projection_declaration"),
            ) from exc

    def box(key: str) -> CasillaId:
        return validated_casilla_id(declared(key), surface=f"projection mapping {key}")

    return ProjectionDeclaration(
        source_modelo=declared("source.modelo"),
        target_modelo=declared("target.modelo"),
        target_period=declared("period.default"),
        target_revision=declared("revision"),
        ingresos=box("source.casilla.ingresos"),
        gastos=box("source.casilla.gastos"),
        rendimiento_neto=box("source.casilla.rendimiento_neto"),
        resultado_final=box("source.casilla.resultado_final"),
        rendimiento_neto_projected=box("target.casilla.rendimiento_neto_projected"),
        base_liquidable_general=box("target.casilla.base_liquidable_general"),
        cuota_integra_estatal=box("target.casilla.cuota_integra_estatal"),
        cuota_integra_autonomica=box("target.casilla.cuota_integra_autonomica"),
        cuota_liquida_estatal=box("target.casilla.cuota_liquida_estatal"),
        cuota_liquida_autonomica=box("target.casilla.cuota_liquida_autonomica"),
        cuota_resultante=box("target.casilla.cuota_resultante"),
        pagos_fraccionados=box("target.casilla.pagos_fraccionados"),
    )


def modelo_projection_available(
    *,
    modelo: str,
    period: Period,
    filing_year: int,
    registry_revision_id: str,
    operation: PinnedAuthorityOperation,
) -> bool:
    """Whether the registry lets this declaration's revision ask for the annual projection.

    The dated cross-model projection declaration names the modelo, period and
    revision it was authored against. A declaration is projectable only when it
    is exactly that target, so the answer follows the registry and never the
    modelo's number. A year the declaration does not reach is not projectable.
    """
    try:
        declaration = registry_projection_declaration(filing_year, operation=operation)
    except GovernedFactNotApplicableError:
        return False
    return (
        declaration.target_modelo == modelo
        and declaration.target_period == period.registry_token
        and declaration.target_revision == registry_revision_id
    )


__all__ = [
    "ProjectionDeclaration",
    "modelo_projection_available",
    "projection_declaration_from",
    "registry_projection_declaration",
]
