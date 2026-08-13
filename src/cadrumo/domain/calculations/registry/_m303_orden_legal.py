"""Legal-reference compiler for annual Orden authority axes."""

from __future__ import annotations

import re
from urllib.parse import parse_qs, urlsplit

from ....core import (
    OrdenAnualIvaAgriculturalIndex,
    OrdenAnualIvaAgriculturalIngresoACuenta,
    OrdenAnualIvaAuthority,
    OrdenAnualIvaDifficultJustification,
    OrdenAnualIvaIngresoACuenta,
    OrdenAnualIvaSeasonalIndex,
    orden_anual_iva_authority_units,
)
from ._errors import RegistryValidationError
from ._ids import LegalRefId
from ._m303_orden_constants import EXTRACTOR_VERSION
from ._m303_orden_keys import (
    activity_legal_key,
    agricultural_index_legal_key,
    agricultural_ingreso_legal_key,
    difficult_justification_legal_key,
    non_agricultural_ingreso_legal_key,
    seasonal_index_legal_key,
)
from ._m303_orden_raw_models import (
    M303AnnualOrdenSourceCensus,
)
from ._m303_orden_source import (
    annual_orden_raw_activity_identity,
    shared_annual_orden_activity_table,
    validate_pinned_boe_orden_source,
)
from ._schema_references import LegalReference, SourceReference


def compile_annual_orden_legal_references(
    census: M303AnnualOrdenSourceCensus,
    *,
    source: SourceReference,
) -> dict[str, LegalReference]:
    """Generate exact legal provisions for every annual-Orden IVA authority axis."""
    validate_pinned_boe_orden_source(source, ejercicio=census.ejercicio)
    if source.id != census.source_ref or source.sha256 != census.source_content_digest:
        raise RegistryValidationError("annual Orden census does not match the source used for legal compilation")
    document_id = _boe_document_id(source)
    if source.applies_from is None or source.applies_to is None:
        raise RegistryValidationError("annual Orden source must retain a closed annual applicability window")
    effective_from = source.applies_from
    effective_to = source.applies_to
    output: dict[str, LegalReference] = {}
    units = orden_anual_iva_authority_units(_shared_annual_orden_authority(census))
    activity_anchors = tuple(unit.anchor for unit in units[: len(census.activities)])
    agricultural_offset = len(census.activities)
    agricultural_index_anchors = tuple(
        unit.anchor for unit in units[agricultural_offset : agricultural_offset + len(census.agricultural_indexes)]
    )
    common_units = units[agricultural_offset + len(census.agricultural_indexes) :]
    if len(common_units) != 4:
        raise RegistryValidationError("annual Orden authority must expose four common axis corpus units")

    def add(
        *,
        key: str,
        axis: str,
        anchor: str,
        article: str,
        section: str,
        required_text: tuple[str, ...],
    ) -> None:
        if key in output:
            raise RegistryValidationError("annual Orden compiler generated duplicate legal identity")
        output[key] = LegalReference(
            id=_axis_legal_ref_id(source, axis=axis, identity=key.rsplit(":", maxsplit=1)[-1]),
            evidence_tier="legal_authority",
            authority="boe",
            kind="orden",
            corpus_ref=f"{source.corpus_path}{anchor}",
            document_id=document_id,
            article=article,
            section=section,
            permalink=source.source_url,
            published_at=source.published_at,
            effective_from=effective_from,
            effective_to=effective_to,
            review_status=source.review_status,
            reviewed_at=source.retrieved_at,
            reviewed_by=f"compiler:{EXTRACTOR_VERSION}",
            required_text=required_text,
        )

    for activity, anchor in zip(census.activities, activity_anchors, strict=True):
        activity_identity = annual_orden_raw_activity_identity(activity)
        add(
            key=activity_legal_key(activity_identity),
            axis="anexo-ii-iva",
            anchor=anchor,
            article=activity.iae_epigrafe,
            section=f"Anexo II. Regimen especial simplificado de IVA: {activity.activity_name}",
            required_text=activity.required_text,
        )
    for index, (item, anchor) in enumerate(zip(census.agricultural_indexes, agricultural_index_anchors, strict=True)):
        add(
            key=agricultural_index_legal_key(index),
            axis="anexo-i-iva-index",
            anchor=anchor,
            article="agricola",
            section=f"Anexo I. Indice de cuota devengada: {item.activity_name}",
            required_text=item.required_text,
        )
    for index, item in enumerate(census.agricultural_ingresos_a_cuenta):
        add(
            key=agricultural_ingreso_legal_key(index),
            axis="anexo-i-iva-ingreso-a-cuenta",
            anchor=common_units[0].anchor,
            article="agricola",
            section=f"Anexo I. Porcentaje de ingreso a cuenta: {item.activity_name}",
            required_text=item.required_text,
        )
    for index, item in enumerate(census.non_agricultural_ingresos_a_cuenta):
        add(
            key=non_agricultural_ingreso_legal_key(index),
            axis="anexo-ii-iva-ingreso-a-cuenta",
            anchor=common_units[1].anchor,
            article=item.iae_epigrafe,
            section=f"Anexo II. Porcentaje de ingreso a cuenta: {item.activity_name}",
            required_text=(item.required_text,),
        )
    for index, item in enumerate(census.seasonal_indexes):
        add(
            key=seasonal_index_legal_key(index),
            axis="iva-indice-temporada",
            anchor=common_units[2].anchor,
            article=f"{item.minimum_days}-{item.maximum_days}",
            section="IVA. Indices correctores por dias de temporada",
            required_text=(item.required_text,),
        )
    add(
        key=difficult_justification_legal_key("agricola"),
        axis="iva-dificil-justificacion-agricola",
        anchor=common_units[3].anchor,
        article="agricola",
        section="IVA. Cuotas soportadas de dificil justificacion",
        required_text=(census.difficult_justification.agricultural_required_text,),
    )
    add(
        key=difficult_justification_legal_key("no_agricola"),
        axis="iva-dificil-justificacion-no-agricola",
        anchor=common_units[3].anchor,
        article="no_agricola",
        section="IVA. Cuotas soportadas de dificil justificacion",
        required_text=(census.difficult_justification.non_agricultural_required_text,),
    )
    return output


def _boe_document_id(source: SourceReference) -> str:
    document_ids = parse_qs(urlsplit(str(source.source_url)).query).get("id", ())
    if len(document_ids) != 1 or re.fullmatch(r"BOE-A-\d{4}-\d+", document_ids[0]) is None:
        raise RegistryValidationError("annual Orden source URL must carry exactly one BOE document id")
    return document_ids[0]


def _axis_legal_ref_id(source: SourceReference, *, axis: str, identity: str) -> LegalRefId:
    source_token = source.id.removeprefix("boe-").removesuffix("-iva-authority")
    return f"{source_token}:{axis}:{identity}"


def _shared_annual_orden_authority(census: M303AnnualOrdenSourceCensus) -> OrdenAnualIvaAuthority:
    """Rebuild the neutral immutable IR solely to reuse its stable corpus anchors."""
    return OrdenAnualIvaAuthority(
        non_agricultural_activities=tuple(shared_annual_orden_activity_table(item) for item in census.activities),
        agricultural_indexes=tuple(
            OrdenAnualIvaAgriculturalIndex(
                annex_heading=item.annex_heading,
                activity_name=item.activity_name,
                cuota_devengada_index=item.cuota_devengada_index,
                required_text=item.required_text,
            )
            for item in census.agricultural_indexes
        ),
        non_agricultural_ingresos_a_cuenta=tuple(
            OrdenAnualIvaIngresoACuenta(
                iae_epigrafe=item.iae_epigrafe,
                activity_name=item.activity_name,
                percentage=item.percentage,
                required_text=item.required_text,
            )
            for item in census.non_agricultural_ingresos_a_cuenta
        ),
        agricultural_ingresos_a_cuenta=tuple(
            OrdenAnualIvaAgriculturalIngresoACuenta(
                annex_heading=item.annex_heading,
                activity_name=item.activity_name,
                percentage=item.percentage,
                required_text=item.required_text,
            )
            for item in census.agricultural_ingresos_a_cuenta
        ),
        seasonal_indexes=tuple(
            OrdenAnualIvaSeasonalIndex(
                minimum_days=item.minimum_days,
                maximum_days=item.maximum_days,
                coefficient=item.coefficient,
                required_text=item.required_text,
            )
            for item in census.seasonal_indexes
        ),
        difficult_justification=OrdenAnualIvaDifficultJustification(
            percentage=census.difficult_justification.percentage,
            agricultural_required_text=census.difficult_justification.agricultural_required_text,
            non_agricultural_required_text=census.difficult_justification.non_agricultural_required_text,
        ),
    )
