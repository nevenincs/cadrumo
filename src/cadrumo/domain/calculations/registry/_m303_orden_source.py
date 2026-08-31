"""Pinned BOE extraction and source-side validation for annual Orden authority."""

from __future__ import annotations

import json
from collections import Counter
from collections.abc import Mapping
from datetime import date
from pathlib import Path
from typing import cast
from urllib.parse import urlsplit

from ....core import (
    OrdenAnualIvaActivityTable,
    OrdenAnualIvaAgriculturalIndex,
    OrdenAnualIvaAgriculturalIngresoACuenta,
    OrdenAnualIvaAuthority,
    OrdenAnualIvaAuthorityUnit,
    OrdenAnualIvaDifficultJustification,
    OrdenAnualIvaIngresoACuenta,
    OrdenAnualIvaLorca2022Reduction,
    OrdenAnualIvaModule,
    OrdenAnualIvaSeasonalIndex,
    extract_orden_anual_iva_authority,
    extract_orden_anual_iva_tables,
    orden_anual_iva_activity_anchors,
    orden_anual_iva_authority_units,
    orden_anual_iva_table_text,
)
from ....core.corpus_sidecar import render_corpus_sidecar_text
from ....core.corpus_text import normalise_corpus_text
from ....core.hashing import sha256_hex
from ....core.external_constants import UTF_8_ENCODING
from ._m303_orden_constants import (
    EXPECTED_ACTIVITY_COUNT,
    EXPECTED_MODULE_DISTRIBUTION,
    EXTRACTOR_VERSION,
)
from ._m303_orden_raw_models import (
    M303AnnualOrdenRawActivity,
    M303AnnualOrdenRawAgriculturalIndex,
    M303AnnualOrdenRawAgriculturalIngresoACuenta,
    M303AnnualOrdenRawDifficultJustification,
    M303AnnualOrdenRawIngresoACuenta,
    M303AnnualOrdenRawLorca2022Reduction,
    M303AnnualOrdenRawModule,
    M303AnnualOrdenRawSeasonalIndex,
    M303AnnualOrdenSourceCensus,
)
from .errors import RegistryLoadError, RegistryValidationError
from .schema_references import SourceReference

_SIDECAR_PREPROCESSOR_ID = "normatives-html"
_SIDECAR_PREPROCESSOR_VERSION = "1.3"
_SIDECAR_SCHEMA_VERSION = "1.0"
_SIDECAR_TOP_LEVEL_KEYS = frozenset(
    {
        "schema_version",
        "source_kind",
        "status",
        "source_relpath",
        "source_sha256",
        "preprocessor_id",
        "preprocessor_version",
        "attribution",
        "units",
    }
)
_SIDECAR_UNIT_KEYS = frozenset({"text", "title", "section", "anchor"})
_BOE_HOST = "www.boe.es"
_CORPUS_PATH_PREFIX = "corpus/normatives/html/"


def validate_pinned_boe_orden_source(source: SourceReference, *, ejercicio: int) -> None:
    """Validate that a source is the official BOE artefact for the full filing year."""
    filing_start = date(ejercicio, 1, 1)
    filing_end = date(ejercicio, 12, 31)
    if source.authority != "boe" or source.kind != "instructions":
        raise RegistryValidationError("annual Orden authority requires a BOE normative instruction source")
    if urlsplit(str(source.source_url)).hostname != _BOE_HOST:
        raise RegistryValidationError("annual Orden authority source must retain its official boe.es URL")
    if not source.corpus_path.startswith(_CORPUS_PATH_PREFIX) or not source.corpus_path.endswith(".html"):
        raise RegistryValidationError("annual Orden authority source must cite a bundled normative HTML artefact")
    if source.applies_from is None or source.applies_from > filing_start:
        raise RegistryValidationError("annual Orden authority source is not pinned from the filing-year start")
    if source.applies_to is None or source.applies_to < filing_end:
        raise RegistryValidationError("annual Orden authority source is not pinned through the filing-year end")


def annual_orden_raw_activity_identity(raw_activity: M303AnnualOrdenRawActivity) -> str:
    """Return the stable digest identity derived from an activity's IAE code and name."""
    identity_seed = f"{raw_activity.iae_epigrafe}\0{raw_activity.activity_name}".encode()
    return sha256_hex(identity_seed)[:20]


def extract_m303_annual_orden_source(
    *,
    ejercicio: int,
    source: SourceReference,
    source_root: Path,
) -> M303AnnualOrdenSourceCensus:
    """Parse one pinned BOE annual Orden directly and reject any incomplete source."""
    validate_pinned_boe_orden_source(source, ejercicio=ejercicio)
    source_path = source_root.expanduser().resolve() / source.corpus_path
    try:
        source_bytes = source_path.read_bytes()
    except OSError as exc:
        raise RegistryLoadError(f"annual Orden source {source.id!r} is unavailable at {source_path}") from exc
    digest = sha256_hex(source_bytes)
    if digest != source.sha256:
        raise RegistryLoadError(
            f"annual Orden source {source.id!r} digest mismatch: expected {source.sha256}, got {digest}",
        )
    if len(source_bytes) != source.bytes:
        raise RegistryLoadError(
            f"annual Orden source {source.id!r} byte count mismatch: expected {source.bytes}, got {len(source_bytes)}",
        )
    parsed_authority = extract_orden_anual_iva_authority(source_bytes, source_label=source.id)
    activities = tuple(_registry_raw_activity(activity) for activity in parsed_authority.non_agricultural_activities)
    try:
        validate_m303_annual_orden_table_shape(activities)
        _validate_annual_orden_sidecar(
            source=source,
            source_root=source_root,
            authority=parsed_authority,
        )
        return M303AnnualOrdenSourceCensus(
            ejercicio=ejercicio,
            source_ref=source.id,
            source_content_digest=source.sha256,
            extractor_version=EXTRACTOR_VERSION,
            activities=activities,
            agricultural_indexes=tuple(
                _registry_raw_agricultural_index(item) for item in parsed_authority.agricultural_indexes
            ),
            non_agricultural_ingresos_a_cuenta=tuple(
                _registry_raw_ingreso_a_cuenta(item) for item in parsed_authority.non_agricultural_ingresos_a_cuenta
            ),
            agricultural_ingresos_a_cuenta=tuple(
                _registry_raw_agricultural_ingreso_a_cuenta(item)
                for item in parsed_authority.agricultural_ingresos_a_cuenta
            ),
            seasonal_indexes=tuple(_registry_raw_seasonal_index(item) for item in parsed_authority.seasonal_indexes),
            difficult_justification=_registry_raw_difficult_justification(parsed_authority.difficult_justification),
            lorca_2022_reduction=_registry_raw_lorca_2022_reduction(parsed_authority.lorca_2022_reduction),
        )
    except (TypeError, ValueError) as exc:
        raise RegistryLoadError(f"annual Orden source {source.id!r} is incomplete or malformed: {exc}") from exc


def extract_m303_annual_orden_tables(
    markup: bytes,
    *,
    source_label: str,
) -> tuple[M303AnnualOrdenRawActivity, ...]:
    """Project the shared pure DOM parser into the registry's strict raw IR."""
    return tuple(
        _registry_raw_activity(activity)
        for activity in extract_orden_anual_iva_tables(markup, source_label=source_label)
    )


def validate_m303_annual_orden_table_shape(activities: tuple[M303AnnualOrdenRawActivity, ...]) -> None:
    """Reject an incomplete or ambiguous annual IVA quota table collection."""
    if len(activities) != EXPECTED_ACTIVITY_COUNT:
        raise RegistryValidationError(
            f"annual Orden source must contain {EXPECTED_ACTIVITY_COUNT} annual IVA activity tables, "
            f"got {len(activities)}",
        )
    module_counts = Counter(len(activity.modules) for activity in activities)
    if module_counts != EXPECTED_MODULE_DISTRIBUTION:
        raise RegistryValidationError(
            f"annual Orden source has an unexpected IVA module distribution: {dict(sorted(module_counts.items()))!r}",
        )
    identities = tuple(annual_orden_raw_activity_identity(activity) for activity in activities)
    if len(set(identities)) != len(identities):
        raise RegistryValidationError("annual Orden source contains ambiguous repeated official activity identities")


def m303_annual_orden_activity_anchor(activity: M303AnnualOrdenRawActivity) -> str:
    """Return the stable semantic sidecar anchor for one annual IVA table."""
    return orden_anual_iva_activity_anchors((shared_annual_orden_activity_table(activity),))[0]


def m303_annual_orden_table_text(activity: M303AnnualOrdenRawActivity) -> str:
    """Render the full lexical evidence of one source-stated annual IVA table."""
    return orden_anual_iva_table_text(shared_annual_orden_activity_table(activity))


def _registry_raw_activity(activity: OrdenAnualIvaActivityTable) -> M303AnnualOrdenRawActivity:
    """Project the parser's neutral IR into the registry's validated raw contract."""
    return M303AnnualOrdenRawActivity(
        annex_heading=activity.annex_heading,
        activity_name=activity.activity_name,
        iae_epigrafe=activity.iae_epigrafe,
        modules=tuple(
            M303AnnualOrdenRawModule(
                order=module.order,
                definition=module.definition,
                unit=module.unit,
                coefficient=module.coefficient,
                required_text=module.required_text,
            )
            for module in activity.modules
        ),
        cuota_minima_pct=activity.cuota_minima_pct,
        required_text=activity.required_text,
    )


def _registry_raw_agricultural_index(
    item: OrdenAnualIvaAgriculturalIndex,
) -> M303AnnualOrdenRawAgriculturalIndex:
    return M303AnnualOrdenRawAgriculturalIndex(
        annex_heading=item.annex_heading,
        activity_name=item.activity_name,
        cuota_devengada_index=item.cuota_devengada_index,
        required_text=item.required_text,
    )


def _registry_raw_ingreso_a_cuenta(item: OrdenAnualIvaIngresoACuenta) -> M303AnnualOrdenRawIngresoACuenta:
    return M303AnnualOrdenRawIngresoACuenta(
        iae_epigrafe=item.iae_epigrafe,
        activity_name=item.activity_name,
        percentage=item.percentage,
        required_text=item.required_text,
    )


def _registry_raw_agricultural_ingreso_a_cuenta(
    item: OrdenAnualIvaAgriculturalIngresoACuenta,
) -> M303AnnualOrdenRawAgriculturalIngresoACuenta:
    return M303AnnualOrdenRawAgriculturalIngresoACuenta(
        annex_heading=item.annex_heading,
        activity_name=item.activity_name,
        percentage=item.percentage,
        required_text=item.required_text,
    )


def _registry_raw_seasonal_index(item: OrdenAnualIvaSeasonalIndex) -> M303AnnualOrdenRawSeasonalIndex:
    return M303AnnualOrdenRawSeasonalIndex(
        minimum_days=item.minimum_days,
        maximum_days=item.maximum_days,
        coefficient=item.coefficient,
        required_text=item.required_text,
    )


def _registry_raw_difficult_justification(
    item: OrdenAnualIvaDifficultJustification,
) -> M303AnnualOrdenRawDifficultJustification:
    return M303AnnualOrdenRawDifficultJustification(
        percentage=item.percentage,
        agricultural_required_text=item.agricultural_required_text,
        non_agricultural_required_text=item.non_agricultural_required_text,
    )


def _registry_raw_lorca_2022_reduction(
    item: OrdenAnualIvaLorca2022Reduction | None,
) -> M303AnnualOrdenRawLorca2022Reduction | None:
    if item is None:
        return None
    return M303AnnualOrdenRawLorca2022Reduction(
        municipality=item.municipality,
        percentage=item.percentage,
        required_text=item.required_text,
    )


def shared_annual_orden_activity_table(activity: M303AnnualOrdenRawActivity) -> OrdenAnualIvaActivityTable:
    """Project registry raw IR back into the neutral table shape for shared helpers."""
    return OrdenAnualIvaActivityTable(
        annex_heading=activity.annex_heading,
        activity_name=activity.activity_name,
        iae_epigrafe=activity.iae_epigrafe,
        modules=tuple(
            OrdenAnualIvaModule(
                order=module.order,
                definition=module.definition,
                unit=module.unit,
                coefficient=module.coefficient,
                required_text=module.required_text,
            )
            for module in activity.modules
        ),
        cuota_minima_pct=activity.cuota_minima_pct,
        required_text=activity.required_text,
    )


def _validate_annual_orden_sidecar(
    *,
    source: SourceReference,
    source_root: Path,
    authority: OrdenAnualIvaAuthority,
) -> None:
    """Require sidecar provenance and complete shared-parser table units.

    This is deliberately normal corpus-unit validation, not a legal resolver
    exception: generated legal references retain ordinary ``path#anchor``
    coordinates and the legal layer resolves them through its generic loader.
    The compiler compares its BOE-parser result to the committed units so a
    stale, partial, duplicate, or independently parsed sidecar cannot supply
    filing authority.
    """
    source_path = source_root.expanduser().resolve() / source.corpus_path
    sidecar_path = source_path.with_name(source_path.name + ".extracted.json")
    try:
        payload_raw: object = json.loads(sidecar_path.read_text(encoding=UTF_8_ENCODING))
    except (OSError, json.JSONDecodeError) as exc:
        raise RegistryLoadError(f"annual Orden sidecar is unreadable for {source.id!r}: {sidecar_path}") from exc
    if not isinstance(payload_raw, dict):
        raise RegistryLoadError(f"annual Orden sidecar is not a JSON object for {source.id!r}")
    payload = cast(Mapping[str, object], payload_raw)
    _validate_sidecar_metadata(payload, source)
    raw_units, rendered_units = _sidecar_units(payload, source)
    text_sidecar_path = source_path.with_name(source_path.name + ".extracted.md")
    try:
        rendered_text = text_sidecar_path.read_text(encoding=UTF_8_ENCODING)
    except OSError as exc:
        raise RegistryLoadError(
            f"annual Orden text sidecar is unreadable for {source.id!r}: {text_sidecar_path}",
        ) from exc
    if rendered_text != render_corpus_sidecar_text(rendered_units):
        raise RegistryLoadError(f"annual Orden sidecar pair diverges for {source.id!r}")

    _validate_sidecar_authority_units(raw_units, authority, source)


def _validate_sidecar_metadata(payload: Mapping[str, object], source: SourceReference) -> None:
    if frozenset(payload) != _SIDECAR_TOP_LEVEL_KEYS:
        raise RegistryLoadError(f"annual Orden sidecar has extra or missing top-level fields for {source.id!r}")
    checks = (
        ("schema_version", _SIDECAR_SCHEMA_VERSION, "annual Orden sidecar has the wrong schema version"),
        ("source_relpath", f"src/cadrumo/_data/{source.corpus_path}", "annual Orden sidecar has the wrong source path"),
        ("source_sha256", source.sha256, "annual Orden sidecar source digest mismatch"),
        ("preprocessor_id", _SIDECAR_PREPROCESSOR_ID, "annual Orden sidecar has the wrong preprocessor id"),
        (
            "preprocessor_version",
            _SIDECAR_PREPROCESSOR_VERSION,
            "annual Orden sidecar has the wrong preprocessor version",
        ),
    )
    if payload.get("source_kind") != "normatives_html" or payload.get("status") != "ok":
        raise RegistryLoadError(f"annual Orden sidecar has the wrong source kind or status for {source.id!r}")
    for key, expected, message in checks:
        if payload.get(key) != expected:
            raise RegistryLoadError(f"{message} for {source.id!r}")
    attribution = payload.get("attribution")
    if not isinstance(attribution, str) or not attribution.strip():
        raise RegistryLoadError(f"annual Orden sidecar has no attribution for {source.id!r}")


def _sidecar_units(
    payload: Mapping[str, object], source: SourceReference
) -> tuple[tuple[Mapping[str, object], ...], list[tuple[str | None, str]]]:
    units = _sidecar_unit_mappings(payload, source)
    return units, [_rendered_sidecar_unit(unit, source) for unit in units]


def _sidecar_unit_mappings(
    payload: Mapping[str, object],
    source: SourceReference,
) -> tuple[Mapping[str, object], ...]:
    raw = payload.get("units")
    if not isinstance(raw, list):
        raise RegistryLoadError(f"annual Orden sidecar has no units list for {source.id!r}")
    raw_values = cast(list[object], raw)
    units = tuple(unit for value in raw_values if (unit := _sidecar_mapping(value)) is not None)
    if len(units) != len(raw_values):
        raise RegistryLoadError(f"annual Orden sidecar contains a non-object unit for {source.id!r}")
    return units


def _rendered_sidecar_unit(
    unit: Mapping[str, object],
    source: SourceReference,
) -> tuple[str | None, str]:
    if frozenset(unit) != _SIDECAR_UNIT_KEYS:
        raise RegistryLoadError(f"annual Orden sidecar unit has extra or missing fields for {source.id!r}")
    title = _optional_sidecar_text(unit.get("title"), source)
    _optional_sidecar_text(unit.get("section"), source)
    _optional_sidecar_text(unit.get("anchor"), source)
    return title, _required_sidecar_text(unit.get("text"), source)


def _optional_sidecar_text(value: object, source: SourceReference) -> str | None:
    if value is None or isinstance(value, str):
        return value
    raise RegistryLoadError(f"annual Orden sidecar contains a non-text unit for {source.id!r}")


def _required_sidecar_text(value: object, source: SourceReference) -> str:
    if isinstance(value, str):
        return value
    raise RegistryLoadError(f"annual Orden sidecar contains a non-text unit for {source.id!r}")


def _validate_sidecar_authority_units(
    units: tuple[Mapping[str, object], ...], authority: OrdenAnualIvaAuthority, source: SourceReference
) -> None:
    expected_by_anchor = _expected_authority_units_by_anchor(authority, source)
    actual, actual_by_anchor = _actual_authority_units_by_anchor(units)
    if len(actual_by_anchor) != len(actual) or set(actual_by_anchor) != set(expected_by_anchor):
        raise RegistryLoadError(
            f"annual Orden sidecar has extra, missing, or cross-year authority units for {source.id!r}"
        )
    _validate_authority_unit_texts(expected_by_anchor, actual_by_anchor, source)


def _expected_authority_units_by_anchor(
    authority: OrdenAnualIvaAuthority,
    source: SourceReference,
) -> dict[str, OrdenAnualIvaAuthorityUnit]:
    expected = orden_anual_iva_authority_units(authority)
    expected_by_anchor = {unit.anchor: unit for unit in expected}
    if len(expected_by_anchor) != len(expected):
        raise RegistryLoadError(f"annual Orden authority units have ambiguous anchors for {source.id!r}")
    return expected_by_anchor


def _actual_authority_units_by_anchor(
    units: tuple[Mapping[str, object], ...],
) -> tuple[tuple[Mapping[str, object], ...], dict[str, Mapping[str, object]]]:
    actual = tuple(
        unit for unit in units if isinstance(unit.get("anchor"), str) and str(unit["anchor"]).startswith("#m303-")
    )
    actual_by_anchor = {str(unit["anchor"]): unit for unit in actual}
    return actual, actual_by_anchor


def _validate_authority_unit_texts(
    expected_by_anchor: Mapping[str, OrdenAnualIvaAuthorityUnit],
    actual_by_anchor: Mapping[str, Mapping[str, object]],
    source: SourceReference,
) -> None:
    for anchor, expected_unit in expected_by_anchor.items():
        unit_text = normalise_corpus_text(str(actual_by_anchor[anchor].get("text")))
        if unit_text != normalise_corpus_text(expected_unit.text):
            raise RegistryLoadError(
                f"annual Orden sidecar authority text differs from the pinned BOE source for {source.id!r} {anchor!r}"
            )


def _sidecar_mapping(value: object) -> Mapping[str, object] | None:
    """Retain only JSON-object sidecar units with an explicit safe value type."""
    return cast(Mapping[str, object], value) if isinstance(value, dict) else None
