"""Development-only projection compiler for annual Orden activity authority."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date

from cadrumo.core.identity.digest import ContentDigest
from cadrumo.core.text_fold import ascii_slug
from cadrumo.domain.calculations.registry.annual_orden_auxiliary_indicator import (
    AnnualOrdenAuxiliaryActivityIndicators,
    resolve_annual_orden_auxiliary_activity_indicators,
)
from cadrumo.domain.calculations.registry.errors import RegistryValidationError
from cadrumo.domain.calculations.registry.governed_fact_scope import governed_facts_in_scope
from cadrumo.domain.calculations.registry.ids import LegalRefId, RevisionId, SourceRefId
from cadrumo.domain.calculations.registry.m303_orden_projection_models import M303AnnualOrdenProjection
from cadrumo.domain.iva.regimen_simplificado_rows import (
    ActividadOrdenAnual,
    AutoridadAgricolaOrdenAnualNoResuelta,
    DificilJustificacionOrdenAnual,
    IndicadorAuxiliarActividad,
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
    lorca_reduction_legal_key,
    non_agricultural_ingreso_legal_key,
    seasonal_index_legal_key,
)
from ._m303_orden_source import annual_orden_raw_activity_identity
from .m303_orden_raw_models import M303AnnualOrdenRawActivity, M303AnnualOrdenSourceCensus


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
    auxiliary_indicators = resolve_annual_orden_auxiliary_activity_indicators(
        effective_date=date(census.ejercicio, 1, 1),
        authority=governed_facts_in_scope(),
    )
    activities = tuple(
        _compile_actividad_orden_anual(
            raw_activity,
            ejercicio=census.ejercicio,
            source_ref=census.source_ref,
            legal_ref=legal_refs[activity_legal_key(annual_orden_raw_activity_identity(raw_activity))],
            auxiliary_indicators=auxiliary_indicators,
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
        lorca_reduction=(
            None
            if census.lorca_reduction is None
            else ReduccionLorcaOrdenAnual.from_registry_source(
                ejercicio=census.ejercicio,
                municipality=census.lorca_reduction.municipality,
                percentage=census.lorca_reduction.percentage,
                legal_ref=legal_refs[lorca_reduction_legal_key()],
                source_ref=census.source_ref,
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
    auxiliary_indicators: AnnualOrdenAuxiliaryActivityIndicators,
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
        auxiliary_activity_indicator=_validated_auxiliary_activity_indicator(
            auxiliary_indicators.for_activity(
                iae_epigrafe=raw_activity.iae_epigrafe,
                activity_code=activity_code,
            ),
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


def _validated_auxiliary_activity_indicator(value: str | None) -> IndicadorAuxiliarActividad | None:
    """Refuse registry indicators outside the M303 activity wire vocabulary."""
    if value is None:
        return None
    if value == "1":
        return "1"
    if value == "2":
        return "2"
    raise RegistryValidationError("annual Orden auxiliary-activity indicator must be '1' or '2'")
