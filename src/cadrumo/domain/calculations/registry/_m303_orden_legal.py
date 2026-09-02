"""Legal-reference compiler for annual Orden authority axes."""

from __future__ import annotations

import re
from datetime import date
from typing import Literal
from urllib.parse import parse_qs, urlsplit

from ....core.orden_anual_html import (
    OrdenAnualIvaAgriculturalIndex,
    OrdenAnualIvaAgriculturalIngresoACuenta,
    OrdenAnualIvaAuthority,
    OrdenAnualIvaDifficultJustification,
    OrdenAnualIvaIngresoACuenta,
    OrdenAnualIvaLorca2022Reduction,
    OrdenAnualIvaSeasonalIndex,
    orden_anual_iva_authority_units,
)
from ....core.revision_review import RevisionReviewStatus
from ._m303_orden_constants import EXTRACTOR_VERSION
from ._m303_orden_keys import (
    activity_legal_key,
    agricultural_index_legal_key,
    agricultural_ingreso_legal_key,
    difficult_justification_legal_key,
    lorca_2022_reduction_legal_key,
    non_agricultural_ingreso_legal_key,
    seasonal_index_legal_key,
)
from ._m303_orden_raw_models import (
    M303AnnualOrdenRawLorca2022Reduction,
    M303AnnualOrdenSourceCensus,
)
from ._m303_orden_source import (
    annual_orden_raw_activity_identity,
    shared_annual_orden_activity_table,
    validate_pinned_boe_orden_source,
)
from .errors import RegistryValidationError
from .ids import LegalRefId
from .schema_references import LegalReference, SourceReference


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
    expected_common_count = 4 + int(census.lorca_2022_reduction is not None)
    if len(common_units) != expected_common_count:
        raise RegistryValidationError("annual Orden authority has the wrong common-axis corpus unit count")

    _compile_activity_legal_references(
        output,
        census=census,
        anchors=activity_anchors,
        source=source,
        document_id=document_id,
        effective_from=effective_from,
        effective_to=effective_to,
    )
    _compile_agricultural_index_legal_references(
        output,
        census=census,
        anchors=agricultural_index_anchors,
        source=source,
        document_id=document_id,
        effective_from=effective_from,
        effective_to=effective_to,
    )
    common_anchors = tuple(unit.anchor for unit in common_units)
    _compile_agricultural_ingreso_legal_references(
        output,
        census=census,
        anchor=common_anchors[0],
        source=source,
        document_id=document_id,
        effective_from=effective_from,
        effective_to=effective_to,
    )
    _compile_non_agricultural_ingreso_legal_references(
        output,
        census=census,
        anchor=common_anchors[1],
        source=source,
        document_id=document_id,
        effective_from=effective_from,
        effective_to=effective_to,
    )
    _compile_seasonal_index_legal_references(
        output,
        census=census,
        anchor=common_anchors[2],
        source=source,
        document_id=document_id,
        effective_from=effective_from,
        effective_to=effective_to,
    )
    _compile_difficult_justification_legal_references(
        output,
        census=census,
        anchor=common_anchors[3],
        source=source,
        document_id=document_id,
        effective_from=effective_from,
        effective_to=effective_to,
    )
    if census.lorca_2022_reduction is not None:
        _compile_lorca_2022_reduction_legal_reference(
            output,
            reduction=census.lorca_2022_reduction,
            anchor=common_anchors[4],
            source=source,
            document_id=document_id,
            effective_from=effective_from,
            effective_to=effective_to,
        )
    return output


def _compile_activity_legal_references(
    output: dict[str, LegalReference],
    *,
    census: M303AnnualOrdenSourceCensus,
    anchors: tuple[str, ...],
    source: SourceReference,
    document_id: str,
    effective_from: date,
    effective_to: date,
) -> None:
    for activity, anchor in zip(census.activities, anchors, strict=True):
        activity_identity = annual_orden_raw_activity_identity(activity)
        _add_annual_orden_legal_reference(
            output,
            source=source,
            document_id=document_id,
            effective_from=effective_from,
            effective_to=effective_to,
            key=activity_legal_key(activity_identity),
            axis="anexo-ii-iva",
            anchor=anchor,
            article=activity.iae_epigrafe,
            section=f"Anexo II. Regimen especial simplificado de IVA: {activity.activity_name}",
            required_text=activity.required_text,
        )


def _compile_agricultural_index_legal_references(
    output: dict[str, LegalReference],
    *,
    census: M303AnnualOrdenSourceCensus,
    anchors: tuple[str, ...],
    source: SourceReference,
    document_id: str,
    effective_from: date,
    effective_to: date,
) -> None:
    for index, (item, anchor) in enumerate(zip(census.agricultural_indexes, anchors, strict=True)):
        _add_annual_orden_legal_reference(
            output,
            source=source,
            document_id=document_id,
            effective_from=effective_from,
            effective_to=effective_to,
            key=agricultural_index_legal_key(index),
            axis="anexo-i-iva-index",
            anchor=anchor,
            article="agricola",
            section=f"Anexo I. Indice de cuota devengada: {item.activity_name}",
            required_text=item.required_text,
        )


def _compile_agricultural_ingreso_legal_references(
    output: dict[str, LegalReference],
    *,
    census: M303AnnualOrdenSourceCensus,
    anchor: str,
    source: SourceReference,
    document_id: str,
    effective_from: date,
    effective_to: date,
) -> None:
    for index, item in enumerate(census.agricultural_ingresos_a_cuenta):
        _add_annual_orden_legal_reference(
            output,
            source=source,
            document_id=document_id,
            effective_from=effective_from,
            effective_to=effective_to,
            key=agricultural_ingreso_legal_key(index),
            axis="anexo-i-iva-ingreso-a-cuenta",
            anchor=anchor,
            article="agricola",
            section=f"Anexo I. Porcentaje de ingreso a cuenta: {item.activity_name}",
            required_text=item.required_text,
        )


def _compile_non_agricultural_ingreso_legal_references(
    output: dict[str, LegalReference],
    *,
    census: M303AnnualOrdenSourceCensus,
    anchor: str,
    source: SourceReference,
    document_id: str,
    effective_from: date,
    effective_to: date,
) -> None:
    for index, item in enumerate(census.non_agricultural_ingresos_a_cuenta):
        _add_annual_orden_legal_reference(
            output,
            source=source,
            document_id=document_id,
            effective_from=effective_from,
            effective_to=effective_to,
            key=non_agricultural_ingreso_legal_key(index),
            axis="anexo-ii-iva-ingreso-a-cuenta",
            anchor=anchor,
            article=item.iae_epigrafe,
            section=f"Anexo II. Porcentaje de ingreso a cuenta: {item.activity_name}",
            required_text=(item.required_text,),
        )


def _compile_seasonal_index_legal_references(
    output: dict[str, LegalReference],
    *,
    census: M303AnnualOrdenSourceCensus,
    anchor: str,
    source: SourceReference,
    document_id: str,
    effective_from: date,
    effective_to: date,
) -> None:
    for index, item in enumerate(census.seasonal_indexes):
        _add_annual_orden_legal_reference(
            output,
            source=source,
            document_id=document_id,
            effective_from=effective_from,
            effective_to=effective_to,
            key=seasonal_index_legal_key(index),
            axis="iva-indice-temporada",
            anchor=anchor,
            article=f"{item.minimum_days}-{item.maximum_days}",
            section="IVA. Indices correctores por dias de temporada",
            required_text=(item.required_text,),
        )


def _compile_difficult_justification_legal_references(
    output: dict[str, LegalReference],
    *,
    census: M303AnnualOrdenSourceCensus,
    anchor: str,
    source: SourceReference,
    document_id: str,
    effective_from: date,
    effective_to: date,
) -> None:
    section = "IVA. Cuotas soportadas de dificil justificacion"
    difficult_axes: tuple[tuple[Literal["agricola", "no_agricola"], str, str], ...] = (
        (
            "agricola",
            "agricola",
            census.difficult_justification.agricultural_required_text,
        ),
        (
            "no_agricola",
            "no_agricola",
            census.difficult_justification.non_agricultural_required_text,
        ),
    )
    for identity, article, required_text in difficult_axes:
        _add_annual_orden_legal_reference(
            output,
            source=source,
            document_id=document_id,
            effective_from=effective_from,
            effective_to=effective_to,
            key=difficult_justification_legal_key(identity),
            axis=f"iva-dificil-justificacion-{identity}",
            anchor=anchor,
            article=article,
            section=section,
            required_text=(required_text,),
        )


def _compile_lorca_2022_reduction_legal_reference(
    output: dict[str, LegalReference],
    *,
    reduction: M303AnnualOrdenRawLorca2022Reduction,
    anchor: str,
    source: SourceReference,
    document_id: str,
    effective_from: date,
    effective_to: date,
) -> None:
    _add_annual_orden_legal_reference(
        output,
        source=source,
        document_id=document_id,
        effective_from=effective_from,
        effective_to=effective_to,
        key=lorca_2022_reduction_legal_key(),
        axis="da-4-lorca-2022-reduction",
        anchor=anchor,
        article="disposición adicional cuarta.2",
        section="Reducción Lorca 2022 de cuota devengada por operaciones corrientes IVA",
        required_text=reduction.required_text,
    )


def _add_annual_orden_legal_reference(
    output: dict[str, LegalReference],
    *,
    source: SourceReference,
    document_id: str,
    effective_from: date,
    effective_to: date,
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
        review_status=RevisionReviewStatus.AGENT_REVIEWED,
        reviewed_at=source.retrieved_at,
        reviewed_by=f"compiler:{EXTRACTOR_VERSION}",
        required_text=required_text,
    )


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
        lorca_2022_reduction=(
            None
            if census.lorca_2022_reduction is None
            else OrdenAnualIvaLorca2022Reduction(
                municipality=census.lorca_2022_reduction.municipality,
                percentage=census.lorca_2022_reduction.percentage,
                required_text=census.lorca_2022_reduction.required_text,
            )
        ),
    )
