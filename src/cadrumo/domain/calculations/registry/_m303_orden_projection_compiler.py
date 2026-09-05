"""Projection compiler for annual Orden registry activity authority."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Literal

from ....core.identity import ContentDigest
from ....core.text_fold import ascii_slug
from ....domain.iva.regimen_simplificado_rows import (
    ActividadOrdenAnual,
    AutoridadAgricolaOrdenAnualNoResuelta,
    DificilJustificacionOrdenAnual,
    IndiceCuotaDevengadaAgricolaOrdenAnual,
    IndiceTemporadaOrdenAnual,
    ModuloOrdenAnual,
    PorcentajeIngresoCuentaAgricolaOrdenAnual,
    PorcentajeIngresoCuentaIaeOrdenAnual,
    ReduccionLorcaOrdenAnual,
)
from ._m303_orden_keys import (
    activity_legal_key,
    agricultural_index_legal_key,
    agricultural_ingreso_legal_key,
    annual_orden_legal_keys,
    difficult_justification_legal_key,
    lorca_2022_reduction_legal_key,
    non_agricultural_ingreso_legal_key,
    seasonal_index_legal_key,
)
from ._m303_orden_raw_models import M303AnnualOrdenRawActivity, M303AnnualOrdenSourceCensus
from ._m303_orden_source import annual_orden_raw_activity_identity
from .errors import RegistryValidationError
from .ids import LegalRefId, RevisionId, SourceRefId
from .m303_orden_projection_models import M303AnnualOrdenProjection

_AUXILIARY_INDICATOR_BY_IAE_AND_ACTIVITY: Mapping[tuple[str, str], Literal["1", "2"]] = {
    ("691.9", "reparacion-de-calzado"): "1",
    (
        "691.9",
        "reparacion-de-otros-bienes-de-consumo-n-c-o-p-excepto-reparacion-de-calzado-restauracion-de-obras-de-arte-muebles-antiguedades-e-instrumentos-musicales",
    ): "2",
    ("722", "transporte-de-mercancias-por-carretera-excepto-residuos"): "1",
    ("722", "transporte-de-residuos-por-carretera"): "2",
}


def compile_m303_annual_orden_projection(
    *,
    census: M303AnnualOrdenSourceCensus,
    registry_revision_id: RevisionId,
    record_design_source_ref: SourceRefId,
    record_design_source_content_digest: ContentDigest,
    legal_refs: Mapping[str, LegalRefId],
) -> M303AnnualOrdenProjection:
    """Compile one validated source census into its immutable registry projection."""
    expected_legal_keys = annual_orden_legal_keys(census)
    if set(legal_refs) != expected_legal_keys:
        raise RegistryValidationError(
            "annual Orden projection must cite exactly its source-scoped legal authority axes",
        )
    activities = tuple(
        _compile_actividad_orden_anual(
            raw_activity,
            ejercicio=census.ejercicio,
            source_ref=census.source_ref,
            legal_ref=legal_refs[activity_legal_key(annual_orden_raw_activity_identity(raw_activity))],
        )
        for raw_activity in census.activities
    )
    return M303AnnualOrdenProjection(
        ejercicio=census.ejercicio,
        registry_revision_id=registry_revision_id,
        source_ref=census.source_ref,
        source_content_digest=census.source_content_digest,
        activities=activities,
        agricultural_authority=AutoridadAgricolaOrdenAnualNoResuelta(
            quota_indexes=tuple(
                IndiceCuotaDevengadaAgricolaOrdenAnual(
                    activity_name=item.activity_name,
                    cuota_devengada_index=item.cuota_devengada_index,
                    legal_refs=(legal_refs[agricultural_index_legal_key(index)],),
                    source_refs=(census.source_ref,),
                )
                for index, item in enumerate(census.agricultural_indexes)
            ),
            ingreso_a_cuenta_percentages=tuple(
                PorcentajeIngresoCuentaAgricolaOrdenAnual(
                    activity_name=item.activity_name,
                    percentage=item.percentage,
                    legal_refs=(legal_refs[agricultural_ingreso_legal_key(index)],),
                    source_refs=(census.source_ref,),
                )
                for index, item in enumerate(census.agricultural_ingresos_a_cuenta)
            ),
            annual_orden_source_ref=census.source_ref,
            record_design_source_ref=record_design_source_ref,
            record_design_source_content_digest=record_design_source_content_digest,
        ),
        non_agricultural_ingresos_a_cuenta=tuple(
            PorcentajeIngresoCuentaIaeOrdenAnual(
                iae_epigrafe=item.iae_epigrafe,
                activity_name=item.activity_name,
                percentage=item.percentage,
                legal_refs=(legal_refs[non_agricultural_ingreso_legal_key(index)],),
                source_refs=(census.source_ref,),
            )
            for index, item in enumerate(census.non_agricultural_ingresos_a_cuenta)
        ),
        seasonal_indexes=tuple(
            IndiceTemporadaOrdenAnual(
                minimum_days=item.minimum_days,
                maximum_days=item.maximum_days,
                coefficient=item.coefficient,
                legal_refs=(legal_refs[seasonal_index_legal_key(index)],),
                source_refs=(census.source_ref,),
            )
            for index, item in enumerate(census.seasonal_indexes)
        ),
        difficult_justification=DificilJustificacionOrdenAnual(
            percentage=census.difficult_justification.percentage,
            legal_refs=(
                legal_refs[difficult_justification_legal_key("agricola")],
                legal_refs[difficult_justification_legal_key("no_agricola")],
            ),
            source_refs=(census.source_ref,),
        ),
        lorca_2022_reduction=(
            None
            if census.lorca_2022_reduction is None
            else ReduccionLorcaOrdenAnual(
                percentage=census.lorca_2022_reduction.percentage,
                legal_refs=(legal_refs[lorca_2022_reduction_legal_key()],),
                source_refs=(census.source_ref,),
                source_content_digest=census.source_content_digest,
            )
        ),
    )


def _compile_actividad_orden_anual(
    raw_activity: M303AnnualOrdenRawActivity,
    *,
    ejercicio: int,
    source_ref: SourceRefId,
    legal_ref: LegalRefId,
) -> ActividadOrdenAnual:
    activity_identity = annual_orden_raw_activity_identity(raw_activity)
    orden_id = f"m303:{ejercicio}:iva:{activity_identity}"
    modules = tuple(
        ModuloOrdenAnual(
            identity=f"{orden_id}:module:{module.order}",
            order=module.order,
            coefficient=module.coefficient,
            legal_refs=(legal_ref,),
            source_refs=(source_ref,),
        )
        for module in raw_activity.modules
    )
    activity_code = _canonical_activity_code(raw_activity.activity_name)
    return ActividadOrdenAnual(
        orden_id=orden_id,
        ejercicio=ejercicio,
        kind="no_agricola",
        activity_code=activity_code,
        iae_epigrafe=raw_activity.iae_epigrafe,
        auxiliary_activity_indicator=_AUXILIARY_INDICATOR_BY_IAE_AND_ACTIVITY.get(
            (raw_activity.iae_epigrafe, activity_code),
        ),
        modulos=modules,
        cuota_minima_pct=raw_activity.cuota_minima_pct,
        applicable_fact_identities=("cuota-devengada-operaciones-corrientes",),
        legal_refs=(legal_ref,),
        source_refs=(source_ref,),
    )


def _canonical_activity_code(activity_name: str) -> str:
    compact = ascii_slug(activity_name)
    if not compact:
        raise RegistryValidationError("annual Orden activity heading has no canonical ASCII identity")
    return compact[:160]
