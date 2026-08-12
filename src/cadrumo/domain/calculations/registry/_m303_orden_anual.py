"""Source-pinned annual Orden taxonomy for Modelo 303's simplified regime.

The annual activity/module catalogue is compiled directly from the bundled BOE
HTML artefact cited by the registry.  Extracted corpus sidecars are search
indexes, not a legal-authority input: their section coverage is intentionally
not relied upon here.
"""

from __future__ import annotations

import json
import re
from collections import Counter
from collections.abc import Iterable, Mapping, Sequence
from datetime import date
from decimal import Decimal
from hashlib import sha256
from pathlib import Path
from typing import TYPE_CHECKING, Literal, cast
from unicodedata import normalize
from urllib.parse import parse_qs, urlsplit

from pydantic import Field, model_validator

from ....core import (
    Modelo,
    OrdenAnualIvaActivityTable,
    OrdenAnualIvaModule,
    extract_orden_anual_iva_tables,
    normalise_corpus_text,
    orden_anual_iva_activity_anchors,
    orden_anual_iva_table_text,
    render_corpus_sidecar_text,
)
from ....core.identity import ContentDigest
from ....domain.iva import (
    ActividadOrdenAnual,
    ActividadOrdenAnualId,
    IaeEpigrafe,
    M303RegimenSimplificadoScopeDecision,
    ModuloOrdenAnual,
)
from ....domain.period import period_end_date
from ._errors import RegistryLoadError, RegistryValidationError
from ._ids import LegalRefId, RevisionId, SourceRefId
from ._loader_cache import toml_file_fingerprint
from ._schema_base import RegistryModel
from ._schema_references import LegalReference, SourceReference

if TYPE_CHECKING:
    from ._schema import ModeloDefinition, RegistrySnapshot


_EXPECTED_ACTIVITY_COUNT = 49
_EXPECTED_MODULE_COUNT = 141
_EXPECTED_MODULE_DISTRIBUTION = {1: 2, 2: 25, 3: 12, 4: 4, 5: 1, 6: 3, 7: 2}
_EXPECTED_MODULE_DISTRIBUTION_VECTOR = (2, 25, 12, 4, 1, 3, 2)
_SUPPORTED_EJERCICIOS = (2023, 2024, 2025, 2026)
_EXTRACTOR_VERSION = "m303-annual-orden-html-v3"
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
_SLUG_RE = re.compile(r"[^a-z0-9]+")


class ActividadOrdenAnualRef(RegistryModel):
    """Immutable reference to one source-pinned annual-Orden activity row."""

    orden_id: ActividadOrdenAnualId
    ejercicio: int = Field(ge=2000, le=2099)
    registry_revision_id: RevisionId
    source_ref: SourceRefId
    source_content_digest: ContentDigest


class M303AnnualOrdenRawModule(RegistryModel):
    """One directly parsed, position-preserving annual IVA quota module."""

    order: int = Field(ge=1, le=7)
    definition: str = Field(min_length=1)
    unit: str = Field(min_length=1)
    coefficient: Decimal = Field(ge=Decimal("0"))
    required_text: str = Field(min_length=1)


class M303AnnualOrdenRawActivity(RegistryModel):
    """One annual IVA quota table as stated by the pinned BOE HTML."""

    annex_heading: Literal["ANEXO II"]
    activity_name: str = Field(min_length=1)
    iae_epigrafe: IaeEpigrafe
    modules: tuple[M303AnnualOrdenRawModule, ...] = Field(min_length=1, max_length=7)
    cuota_minima_pct: Decimal = Field(ge=Decimal("0"), le=Decimal("100"))
    required_text: tuple[str, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def _module_rows_are_complete_and_ordered(self) -> M303AnnualOrdenRawActivity:
        if tuple(module.order for module in self.modules) != tuple(range(1, len(self.modules) + 1)):
            raise RegistryValidationError("annual Orden module rows must be complete and ordered from one")
        return self


class M303AnnualOrdenSourceCensus(RegistryModel):
    """Complete, digest-bound extraction of one official annual Orden source."""

    ejercicio: int = Field(ge=2000, le=2099)
    source_ref: SourceRefId
    source_content_digest: ContentDigest
    extractor_version: str = Field(min_length=1)
    activities: tuple[M303AnnualOrdenRawActivity, ...] = Field(min_length=_EXPECTED_ACTIVITY_COUNT)

    @model_validator(mode="after")
    def _has_the_complete_official_annual_quota_catalogue(self) -> M303AnnualOrdenSourceCensus:
        if len(self.activities) != _EXPECTED_ACTIVITY_COUNT:
            raise RegistryValidationError(
                f"annual Orden source must contain {_EXPECTED_ACTIVITY_COUNT} annual IVA activity tables, "
                f"got {len(self.activities)}",
            )
        module_counts = Counter(len(activity.modules) for activity in self.activities)
        if module_counts != _EXPECTED_MODULE_DISTRIBUTION:
            raise RegistryValidationError(
                "annual Orden source has an unexpected IVA module distribution: "
                f"{dict(sorted(module_counts.items()))!r}",
            )
        if sum(module_counts.values()) != _EXPECTED_ACTIVITY_COUNT:
            raise RegistryValidationError("annual Orden source activity table count is internally inconsistent")
        total_modules = sum(module_count * occurrences for module_count, occurrences in module_counts.items())
        if total_modules != _EXPECTED_MODULE_COUNT:
            raise RegistryValidationError(
                f"annual Orden source must contain {_EXPECTED_MODULE_COUNT} IVA module rows",
            )
        return self


class M303AnnualOrdenGeneratedSource(RegistryModel):
    """One source-level invariant emitted by the annual Orden generator."""

    ejercicio: int = Field(ge=2000, le=2099)
    source_ref: SourceRefId
    source_content_digest: ContentDigest
    activity_table_count: int = Field(ge=1)
    module_row_count: int = Field(ge=1)
    module_distribution: tuple[int, ...] = Field(min_length=7, max_length=7)

    @model_validator(mode="after")
    def _is_the_exact_supported_annual_quota_shape(self) -> M303AnnualOrdenGeneratedSource:
        if self.activity_table_count != _EXPECTED_ACTIVITY_COUNT:
            raise RegistryValidationError("annual Orden manifest has the wrong activity table count")
        if self.module_row_count != _EXPECTED_MODULE_COUNT:
            raise RegistryValidationError("annual Orden manifest has the wrong module row count")
        if self.module_distribution != _EXPECTED_MODULE_DISTRIBUTION_VECTOR:
            raise RegistryValidationError("annual Orden manifest has the wrong module distribution")
        return self


class M303AnnualOrdenGeneratedManifest(RegistryModel):
    """Checked registry artefact that pins the source compiler's exact output."""

    extractor_version: str = Field(min_length=1)
    sources: tuple[M303AnnualOrdenGeneratedSource, ...] = Field(min_length=4, max_length=4)

    @model_validator(mode="after")
    def _has_one_complete_source_per_supported_year(self) -> M303AnnualOrdenGeneratedManifest:
        if self.extractor_version != _EXTRACTOR_VERSION:
            raise RegistryValidationError("annual Orden manifest was generated by an incompatible extractor")
        if tuple(item.ejercicio for item in self.sources) != _SUPPORTED_EJERCICIOS:
            raise RegistryValidationError(
                "annual Orden manifest must list each supported ejercicio exactly once in order",
            )
        if len({item.source_ref for item in self.sources}) != len(self.sources):
            raise RegistryValidationError("annual Orden manifest cannot reuse a source across annual exercises")
        return self


class M303AnnualOrdenCompilation(RegistryModel):
    """Transient compiler output folded directly onto the registry catalogues."""

    authority: M303AnnualOrdenAuthority
    legal: Mapping[LegalRefId, LegalReference]


class M303AnnualOrdenProjection(RegistryModel):
    """Immutable taxonomy for one Modelo 303 year/revision/source coordinate."""

    ejercicio: int = Field(ge=2000, le=2099)
    registry_revision_id: RevisionId
    source_ref: SourceRefId
    source_content_digest: ContentDigest
    activities: tuple[ActividadOrdenAnual, ...] = Field(min_length=_EXPECTED_ACTIVITY_COUNT)

    @model_validator(mode="after")
    def _rows_are_complete_and_year_scoped(self) -> M303AnnualOrdenProjection:
        if len(self.activities) != _EXPECTED_ACTIVITY_COUNT:
            raise RegistryValidationError("annual Orden projection is incomplete")
        if any(activity.ejercicio != self.ejercicio for activity in self.activities):
            raise RegistryValidationError("annual Orden activities must match their projection ejercicio")
        ids = tuple(activity.orden_id for activity in self.activities)
        if len(set(ids)) != len(ids):
            raise RegistryValidationError("annual Orden projection contains duplicate orden_id values")
        return self


class M303AnnualOrdenAuthority(RegistryModel):
    """Compiled annual-Orden projections, retained solely by registry snapshots."""

    projections: tuple[M303AnnualOrdenProjection, ...] = ()

    @classmethod
    def empty(cls) -> M303AnnualOrdenAuthority:
        """Return an explicitly unresolved state; production M303 resolution refuses it."""
        return cls(projections=())

    @model_validator(mode="after")
    def _projection_coordinates_are_unique(self) -> M303AnnualOrdenAuthority:
        coordinates = tuple((item.ejercicio, item.registry_revision_id) for item in self.projections)
        if len(set(coordinates)) != len(coordinates):
            raise RegistryValidationError("annual Orden authority contains ambiguous year/revision projections")
        return self


class M303AnnualOrdenSnapshot(RegistryModel):
    """The source-bound annual Orden resolved for one filing snapshot."""

    ejercicio: int = Field(ge=2000, le=2099)
    registry_revision_id: RevisionId
    source_ref: SourceRefId
    source_content_digest: ContentDigest
    activities: tuple[ActividadOrdenAnual, ...] = Field(min_length=_EXPECTED_ACTIVITY_COUNT)
    activity_refs: tuple[ActividadOrdenAnualRef, ...] = Field(min_length=_EXPECTED_ACTIVITY_COUNT)

    @model_validator(mode="after")
    def _references_match_the_activity_rows(self) -> M303AnnualOrdenSnapshot:
        if tuple(item.orden_id for item in self.activities) != tuple(item.orden_id for item in self.activity_refs):
            raise RegistryValidationError("annual Orden snapshot refs must exactly match its activity rows")
        expected_coordinate = (
            self.ejercicio,
            self.registry_revision_id,
            self.source_ref,
            self.source_content_digest,
        )
        if any(
            (
                item.ejercicio,
                item.registry_revision_id,
                item.source_ref,
                item.source_content_digest,
            )
            != expected_coordinate
            for item in self.activity_refs
        ):
            raise RegistryValidationError("annual Orden snapshot refs must retain its exact source coordinate")
        if any(
            activity.ejercicio != self.ejercicio or self.source_ref not in activity.source_refs
            for activity in self.activities
        ):
            raise RegistryValidationError("annual Orden snapshot activities must retain its exact source coordinate")
        return self


class M303RegimenSimplificadoSnapshot(RegistryModel):
    """One resolved M303 annual-Orden, scope, and record-design coordinate."""

    scope_decision: M303RegimenSimplificadoScopeDecision
    orden: M303AnnualOrdenSnapshot
    record_design: SourceReference

    @model_validator(mode="after")
    def _requires_complete_s59_coordinates(self) -> M303RegimenSimplificadoSnapshot:
        if self.record_design.kind != "record_design" or self.record_design.record_design_epoch is None:
            raise RegistryValidationError("M303 regimen simplificado snapshot requires an epoch-pinned record design")
        return self


def extract_m303_annual_orden_source(
    *,
    ejercicio: int,
    source: SourceReference,
    source_root: Path,
) -> M303AnnualOrdenSourceCensus:
    """Parse one pinned BOE annual Orden directly and reject any incomplete source."""
    _validate_pinned_boe_orden_source(source, ejercicio=ejercicio)
    source_path = source_root.expanduser().resolve() / source.corpus_path
    try:
        source_bytes = source_path.read_bytes()
    except OSError as exc:
        raise RegistryLoadError(f"annual Orden source {source.id!r} is unavailable at {source_path}") from exc
    digest = sha256(source_bytes).hexdigest()
    if digest != source.sha256:
        raise RegistryLoadError(
            f"annual Orden source {source.id!r} digest mismatch: expected {source.sha256}, got {digest}",
        )
    if len(source_bytes) != source.bytes:
        raise RegistryLoadError(
            f"annual Orden source {source.id!r} byte count mismatch: expected {source.bytes}, got {len(source_bytes)}",
        )
    activities = extract_m303_annual_orden_tables(source_bytes, source_label=source.id)
    try:
        validate_m303_annual_orden_table_shape(activities)
        _validate_annual_orden_sidecar(
            source=source,
            source_root=source_root,
            activities=activities,
        )
        return M303AnnualOrdenSourceCensus(
            ejercicio=ejercicio,
            source_ref=source.id,
            source_content_digest=source.sha256,
            extractor_version=_EXTRACTOR_VERSION,
            activities=activities,
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
    if len(activities) != _EXPECTED_ACTIVITY_COUNT:
        raise RegistryValidationError(
            f"annual Orden source must contain {_EXPECTED_ACTIVITY_COUNT} annual IVA activity tables, "
            f"got {len(activities)}",
        )
    module_counts = Counter(len(activity.modules) for activity in activities)
    if module_counts != _EXPECTED_MODULE_DISTRIBUTION:
        raise RegistryValidationError(
            f"annual Orden source has an unexpected IVA module distribution: {dict(sorted(module_counts.items()))!r}",
        )
    identities = tuple(_raw_activity_identity(activity) for activity in activities)
    if len(set(identities)) != len(identities):
        raise RegistryValidationError("annual Orden source contains ambiguous repeated official activity identities")


def m303_annual_orden_activity_anchor(activity: M303AnnualOrdenRawActivity) -> str:
    """Return the stable semantic sidecar anchor for one annual IVA table."""
    return orden_anual_iva_activity_anchors((_shared_activity_table(activity),))[0]


def m303_annual_orden_table_text(activity: M303AnnualOrdenRawActivity) -> str:
    """Render the full lexical evidence of one source-stated annual IVA table."""
    return orden_anual_iva_table_text(_shared_activity_table(activity))


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


def _shared_activity_table(activity: M303AnnualOrdenRawActivity) -> OrdenAnualIvaActivityTable:
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
    activities: tuple[M303AnnualOrdenRawActivity, ...],
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
        payload_raw: object = json.loads(sidecar_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RegistryLoadError(f"annual Orden sidecar is unreadable for {source.id!r}: {sidecar_path}") from exc
    if not isinstance(payload_raw, dict):
        raise RegistryLoadError(f"annual Orden sidecar is not a JSON object for {source.id!r}")
    payload = cast(Mapping[str, object], payload_raw)
    _validate_sidecar_metadata(payload, source)
    raw_units, rendered_units = _sidecar_units(payload, source)
    text_sidecar_path = source_path.with_name(source_path.name + ".extracted.md")
    try:
        rendered_text = text_sidecar_path.read_text(encoding="utf-8")
    except OSError as exc:
        raise RegistryLoadError(
            f"annual Orden text sidecar is unreadable for {source.id!r}: {text_sidecar_path}",
        ) from exc
    if rendered_text != render_corpus_sidecar_text(rendered_units):
        raise RegistryLoadError(f"annual Orden sidecar pair diverges for {source.id!r}")

    _validate_sidecar_tables(raw_units, activities, source)


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


def _validate_sidecar_tables(
    units: tuple[Mapping[str, object], ...], activities: tuple[M303AnnualOrdenRawActivity, ...], source: SourceReference
) -> None:
    anchors = _validated_annual_orden_anchors(activities, source)
    units_by_anchor = _annual_sidecar_units_by_anchor(units, anchors=anchors, source=source)
    for activity, anchor in zip(activities, anchors, strict=True):
        unit_text = normalise_corpus_text(str(units_by_anchor[anchor].get("text")))
        if unit_text != normalise_corpus_text(m303_annual_orden_table_text(activity)):
            raise RegistryLoadError(
                f"annual Orden sidecar table cells differ from the pinned BOE source for {source.id!r} {anchor!r}"
            )


def _validated_annual_orden_anchors(
    activities: tuple[M303AnnualOrdenRawActivity, ...],
    source: SourceReference,
) -> tuple[str, ...]:
    anchors = orden_anual_iva_activity_anchors(tuple(_shared_activity_table(activity) for activity in activities))
    if len(set(anchors)) != _EXPECTED_ACTIVITY_COUNT:
        raise RegistryLoadError(f"annual Orden sidecar anchors are ambiguous for {source.id!r}")
    return anchors


def _annual_sidecar_units_by_anchor(
    units: tuple[Mapping[str, object], ...],
    *,
    anchors: tuple[str, ...],
    source: SourceReference,
) -> dict[str, Mapping[str, object]]:
    annual_units = tuple(
        unit
        for unit in units
        if isinstance(unit.get("anchor"), str) and str(unit["anchor"]).startswith("#m303-anexo-ii-iva-")
    )
    if len(annual_units) != _EXPECTED_ACTIVITY_COUNT or {unit["anchor"] for unit in annual_units} != set(anchors):
        raise RegistryLoadError(f"annual Orden sidecar has extra, missing, or cross-year table units for {source.id!r}")
    return {str(unit["anchor"]): unit for unit in annual_units}


def _sidecar_mapping(value: object) -> Mapping[str, object] | None:
    """Retain only JSON-object sidecar units with an explicit safe value type."""
    return cast(Mapping[str, object], value) if isinstance(value, dict) else None


def compile_m303_annual_orden_projection(
    *,
    census: M303AnnualOrdenSourceCensus,
    registry_revision_id: RevisionId,
    legal_refs_by_activity: Mapping[str, LegalRefId],
) -> M303AnnualOrdenProjection:
    """Compile one validated source census into its immutable registry projection."""
    identities = tuple(_raw_activity_identity(activity) for activity in census.activities)
    if set(legal_refs_by_activity) != set(identities):
        raise RegistryValidationError(
            "annual Orden projection must cite exactly one table-scoped LegalReference per activity",
        )
    activities = tuple(
        _compile_actividad_orden_anual(
            raw_activity,
            ejercicio=census.ejercicio,
            source_ref=census.source_ref,
            legal_ref=legal_refs_by_activity[_raw_activity_identity(raw_activity)],
        )
        for raw_activity in census.activities
    )
    return M303AnnualOrdenProjection(
        ejercicio=census.ejercicio,
        registry_revision_id=registry_revision_id,
        source_ref=census.source_ref,
        source_content_digest=census.source_content_digest,
        activities=activities,
    )


def generate_m303_annual_orden_manifest(
    *,
    source_root: Path,
    sources: Mapping[SourceRefId, SourceReference],
) -> M303AnnualOrdenGeneratedManifest:
    """Derive the exact source-integrity manifest from the pinned BOE corpus."""
    generated_sources: list[M303AnnualOrdenGeneratedSource] = []
    for ejercicio in _SUPPORTED_EJERCICIOS:
        source = _single_annual_orden_source_for_year(sources, ejercicio=ejercicio)
        census = extract_m303_annual_orden_source(
            ejercicio=ejercicio,
            source=source,
            source_root=source_root,
        )
        generated_sources.append(
            M303AnnualOrdenGeneratedSource(
                ejercicio=ejercicio,
                source_ref=source.id,
                source_content_digest=census.source_content_digest,
                activity_table_count=len(census.activities),
                module_row_count=sum(len(activity.modules) for activity in census.activities),
                module_distribution=tuple(
                    sum(len(activity.modules) == size for activity in census.activities) for size in range(1, 8)
                ),
            ),
        )
    return M303AnnualOrdenGeneratedManifest(
        extractor_version=_EXTRACTOR_VERSION,
        sources=tuple(generated_sources),
    )


def render_m303_annual_orden_manifest(
    *,
    source_root: Path,
    sources: Mapping[SourceRefId, SourceReference],
) -> str:
    """Render the generated registry artefact in canonical TOML order."""
    manifest = generate_m303_annual_orden_manifest(source_root=source_root, sources=sources)
    lines = [
        "# Generated by dev.registry.m303_orden_anual; do not edit by hand.",
        "[generator]",
        f'extractor_version = "{manifest.extractor_version}"',
        "",
    ]
    for source in manifest.sources:
        lines.extend(
            (
                "[[sources]]",
                f"ejercicio = {source.ejercicio}",
                f'source_ref = "{source.source_ref}"',
                f'source_content_digest = "{source.source_content_digest}"',
                f"activity_table_count = {source.activity_table_count}",
                f"module_row_count = {source.module_row_count}",
                "module_distribution = [" + ", ".join(str(value) for value in source.module_distribution) + "]",
                "",
            ),
        )
    return "\n".join(lines)


def check_m303_annual_orden_manifest(
    *,
    manifest_path: Path,
    source_root: Path,
    sources: Mapping[SourceRefId, SourceReference],
) -> M303AnnualOrdenGeneratedManifest:
    """Refuse a missing, manually edited, or stale generated annual Orden artefact."""
    try:
        directory_entries = tuple(manifest_path.parent.iterdir())
    except OSError as exc:
        raise RegistryLoadError(f"annual Orden generated directory cannot be read: {manifest_path.parent}") from exc
    unexpected_entries = tuple(entry for entry in directory_entries if entry.name != manifest_path.name)
    if unexpected_entries:
        names = ", ".join(sorted(entry.name for entry in unexpected_entries))
        raise RegistryLoadError(f"annual Orden generated directory contains unexpected entries: {names}")
    if not manifest_path.is_file():
        raise RegistryLoadError(f"annual Orden generated manifest is missing: {manifest_path}")
    expected = render_m303_annual_orden_manifest(source_root=source_root, sources=sources)
    try:
        actual = manifest_path.read_text(encoding="utf-8")
    except OSError as exc:
        raise RegistryLoadError(f"annual Orden generated manifest cannot be read: {manifest_path}") from exc
    if actual != expected:
        raise RegistryLoadError(f"annual Orden generated manifest is stale: regenerate {manifest_path}")
    return generate_m303_annual_orden_manifest(source_root=source_root, sources=sources)


def load_m303_annual_orden_authority(
    root: Path,
    *,
    source_root: Path,
    modelos: Sequence[ModeloDefinition],
    sources: Mapping[SourceRefId, SourceReference],
) -> M303AnnualOrdenCompilation:
    """Compile source-pinned annual Orden rows and legal provisions into the registry."""
    manifest_path = root.resolve() / "m303_orden_anual" / "manifest.toml"
    manifest = check_m303_annual_orden_manifest(
        manifest_path=manifest_path,
        source_root=source_root,
        sources=sources,
    )
    modelo_303 = _single_m303_modelo(modelos)
    annual_source_refs = frozenset(source.source_ref for source in manifest.sources)
    legal: dict[LegalRefId, LegalReference] = {}
    projections: list[M303AnnualOrdenProjection] = []
    for generated_source in manifest.sources:
        source, census, table_legal_refs = _compile_generated_annual_orden_source(
            generated_source,
            source_root=source_root,
            sources=sources,
        )
        _merge_annual_orden_legal_refs(legal, table_legal_refs.values())
        projections.extend(
            _annual_orden_projections_for_source(
                census=census,
                source=source,
                modelo_303=modelo_303,
                annual_source_refs=annual_source_refs,
                table_legal_refs=table_legal_refs,
            )
        )
    return M303AnnualOrdenCompilation(authority=M303AnnualOrdenAuthority(projections=tuple(projections)), legal=legal)


def _compile_generated_annual_orden_source(
    generated_source: M303AnnualOrdenGeneratedSource,
    *,
    source_root: Path,
    sources: Mapping[SourceRefId, SourceReference],
) -> tuple[SourceReference, M303AnnualOrdenSourceCensus, dict[str, LegalReference]]:
    source = sources.get(generated_source.source_ref)
    if source is None:
        raise RegistryLoadError(f"annual Orden manifest names unknown source {generated_source.source_ref!r}")
    census = extract_m303_annual_orden_source(
        ejercicio=generated_source.ejercicio,
        source=source,
        source_root=source_root,
    )
    _validate_generated_source_matches_census(generated_source, census)
    table_legal_refs = _compile_table_legal_references(census, source=source)
    return source, census, table_legal_refs


def _annual_orden_projections_for_source(
    *,
    census: M303AnnualOrdenSourceCensus,
    source: SourceReference,
    modelo_303: ModeloDefinition,
    annual_source_refs: frozenset[SourceRefId],
    table_legal_refs: Mapping[str, LegalReference],
) -> tuple[M303AnnualOrdenProjection, ...]:
    projections: list[M303AnnualOrdenProjection] = []
    for revision in modelo_303.revisions.values():
        if not revision.period_selector.includes_year(census.ejercicio):
            continue
        if source.id not in revision.source_refs:
            raise RegistryValidationError(
                f"Modelo 303 revision {revision.id!r} does not cite annual Orden source {source.id!r}",
            )
        cited_annual_sources = frozenset(revision.source_refs).intersection(annual_source_refs)
        if cited_annual_sources != frozenset({source.id}):
            raise RegistryValidationError(
                f"Modelo 303 revision {revision.id!r} must cite exactly its filing-year annual Orden source",
            )
        projections.append(
            compile_m303_annual_orden_projection(
                census=census,
                registry_revision_id=revision.id,
                legal_refs_by_activity={identity: legal_ref.id for identity, legal_ref in table_legal_refs.items()},
            ),
        )
    return tuple(projections)


def _merge_annual_orden_legal_refs(
    legal: dict[LegalRefId, LegalReference],
    generated_refs: Iterable[LegalReference],
) -> None:
    for legal_ref in generated_refs:
        if legal_ref.id in legal:
            raise RegistryValidationError(f"annual Orden compiler generated duplicate legal ref {legal_ref.id!r}")
        legal[legal_ref.id] = legal_ref


def collect_m303_annual_orden_fingerprints(root: Path) -> tuple[tuple[str, int, int, str], ...]:
    """Fingerprint the generated manifest and no hand-authored annual rows."""
    directory = root.resolve() / "m303_orden_anual"
    if not directory.is_dir():
        return ()
    return tuple(toml_file_fingerprint(path.resolve()) for path in sorted(directory.glob("*.toml")))


def _single_annual_orden_source_for_year(
    sources: Mapping[SourceRefId, SourceReference],
    *,
    ejercicio: int,
) -> SourceReference:
    filing_start = date(ejercicio, 1, 1)
    filing_end = date(ejercicio, 12, 31)
    candidates = tuple(
        source
        for source in sources.values()
        if source.id.endswith("-iva-authority")
        and source.authority == "boe"
        and source.kind == "instructions"
        and source.applies_from == filing_start
        and source.applies_to == filing_end
    )
    if len(candidates) != 1:
        raise RegistryValidationError(
            f"annual Orden compiler requires exactly one pinned BOE source for ejercicio {ejercicio}, "
            f"got {len(candidates)}",
        )
    return candidates[0]


def _single_m303_modelo(modelos: Sequence[ModeloDefinition]) -> ModeloDefinition:
    candidates = tuple(modelo for modelo in modelos if modelo.id == Modelo.M303)
    if len(candidates) != 1:
        raise RegistryValidationError(f"annual Orden compiler requires exactly one Modelo 303, got {len(candidates)}")
    return candidates[0]


def _validate_generated_source_matches_census(
    generated: M303AnnualOrdenGeneratedSource,
    census: M303AnnualOrdenSourceCensus,
) -> None:
    actual_distribution = tuple(
        sum(len(activity.modules) == size for activity in census.activities) for size in range(1, 8)
    )
    if generated.source_ref != census.source_ref or generated.source_content_digest != census.source_content_digest:
        raise RegistryValidationError("annual Orden generated source no longer matches its pinned source identity")
    if generated.activity_table_count != len(census.activities):
        raise RegistryValidationError("annual Orden generated source activity count no longer matches the BOE HTML")
    if generated.module_row_count != sum(len(activity.modules) for activity in census.activities):
        raise RegistryValidationError("annual Orden generated source module count no longer matches the BOE HTML")
    if generated.module_distribution != actual_distribution:
        raise RegistryValidationError(
            "annual Orden generated source module distribution no longer matches the BOE HTML",
        )


def _compile_table_legal_references(
    census: M303AnnualOrdenSourceCensus,
    *,
    source: SourceReference,
) -> dict[str, LegalReference]:
    """Generate one exact, table-scoped legal provision for every annual IVA table."""
    _validate_pinned_boe_orden_source(source, ejercicio=census.ejercicio)
    if source.id != census.source_ref or source.sha256 != census.source_content_digest:
        raise RegistryValidationError("annual Orden census does not match the source used for legal compilation")
    document_id = _boe_document_id(source)
    if source.applies_from is None or source.applies_to is None:
        raise RegistryValidationError("annual Orden source must retain a closed annual applicability window")
    output: dict[str, LegalReference] = {}
    anchors = orden_anual_iva_activity_anchors(
        tuple(_shared_activity_table(activity) for activity in census.activities)
    )
    for activity, anchor in zip(census.activities, anchors, strict=True):
        activity_identity = _raw_activity_identity(activity)
        legal_id = _table_legal_ref_id(source, activity_identity)
        if activity_identity in output:
            raise RegistryValidationError("annual Orden compiler generated duplicate activity legal identity")
        output[activity_identity] = LegalReference(
            id=legal_id,
            evidence_tier="legal_authority",
            authority="boe",
            kind="orden",
            corpus_ref=f"{source.corpus_path}{anchor}",
            document_id=document_id,
            article=activity.iae_epigrafe,
            section=f"Anexo II. Regimen especial simplificado de IVA: {activity.activity_name}",
            permalink=source.source_url,
            published_at=source.published_at,
            effective_from=source.applies_from,
            effective_to=source.applies_to,
            review_status=source.review_status,
            reviewed_at=source.retrieved_at,
            reviewed_by=f"compiler:{_EXTRACTOR_VERSION}",
            required_text=activity.required_text,
        )
    return output


def _boe_document_id(source: SourceReference) -> str:
    document_ids = parse_qs(urlsplit(str(source.source_url)).query).get("id", ())
    if len(document_ids) != 1 or re.fullmatch(r"BOE-A-\d{4}-\d+", document_ids[0]) is None:
        raise RegistryValidationError("annual Orden source URL must carry exactly one BOE document id")
    return document_ids[0]


def _table_legal_ref_id(source: SourceReference, activity_identity: str) -> LegalRefId:
    source_token = source.id.removeprefix("boe-").removesuffix("-iva-authority")
    return f"{source_token}:anexo-ii-iva:{activity_identity}"


def resolve_m303_regimen_simplificado_snapshot(
    *,
    registry_snapshot: RegistrySnapshot,
    scope_decision: M303RegimenSimplificadoScopeDecision,
) -> M303RegimenSimplificadoSnapshot:
    """Resolve the sole annual-Orden and record-design snapshot for an explicit scope input."""
    if registry_snapshot.modelo.id != Modelo.M303:
        raise RegistryValidationError("M303 regimen simplificado resolver requires a Modelo 303 registry snapshot")
    record_design = _unique_active_record_design(
        sources=registry_snapshot.sources,
        revision_source_refs=registry_snapshot.revision.source_refs,
        filing_year=registry_snapshot.filing_year,
        period=registry_snapshot.period,
    )
    projection = _select_m303_annual_orden_projection(registry_snapshot)
    return M303RegimenSimplificadoSnapshot(
        scope_decision=scope_decision,
        orden=M303AnnualOrdenSnapshot(
            ejercicio=projection.ejercicio,
            registry_revision_id=projection.registry_revision_id,
            source_ref=projection.source_ref,
            source_content_digest=projection.source_content_digest,
            activities=projection.activities,
            activity_refs=tuple(
                ActividadOrdenAnualRef(
                    orden_id=activity.orden_id,
                    ejercicio=projection.ejercicio,
                    registry_revision_id=projection.registry_revision_id,
                    source_ref=projection.source_ref,
                    source_content_digest=projection.source_content_digest,
                )
                for activity in projection.activities
            ),
        ),
        record_design=record_design,
    )


def _select_m303_annual_orden_projection(registry_snapshot: RegistrySnapshot) -> M303AnnualOrdenProjection:
    """Select the internal projection consumed only by the canonical resolver."""
    if registry_snapshot.modelo.id != Modelo.M303:
        raise RegistryValidationError("annual Orden projection selector requires a Modelo 303 registry snapshot")
    candidates = tuple(
        item
        for item in registry_snapshot.m303_annual_orden.projections
        if item.ejercicio == registry_snapshot.filing_year
        and item.registry_revision_id == registry_snapshot.revision.id
    )
    if not candidates:
        raise RegistryValidationError(
            "modelo 303 annual Orden authority has no projection for "
            f"ejercicio {registry_snapshot.filing_year} revision {registry_snapshot.revision.id!r}",
        )
    if len(candidates) != 1:
        raise RegistryValidationError(
            "modelo 303 annual Orden authority is ambiguous for "
            f"ejercicio {registry_snapshot.filing_year} revision {registry_snapshot.revision.id!r}",
        )
    return candidates[0]


def _validate_pinned_boe_orden_source(source: SourceReference, *, ejercicio: int) -> None:
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


def _compile_actividad_orden_anual(
    raw_activity: M303AnnualOrdenRawActivity,
    *,
    ejercicio: int,
    source_ref: SourceRefId,
    legal_ref: LegalRefId,
) -> ActividadOrdenAnual:
    activity_identity = _raw_activity_identity(raw_activity)
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
    return ActividadOrdenAnual(
        orden_id=orden_id,
        ejercicio=ejercicio,
        kind="no_agricola",
        activity_code=_canonical_activity_code(raw_activity.activity_name),
        iae_epigrafe=raw_activity.iae_epigrafe,
        modulos=modules,
        cuota_minima_pct=raw_activity.cuota_minima_pct,
        applicable_fact_identities=("cuota-devengada-operaciones-corrientes",),
        legal_refs=(legal_ref,),
        source_refs=(source_ref,),
    )


def _raw_activity_identity(raw_activity: M303AnnualOrdenRawActivity) -> str:
    identity_seed = f"{raw_activity.iae_epigrafe}\0{raw_activity.activity_name}".encode()
    return sha256(identity_seed).hexdigest()[:20]


def _canonical_activity_code(activity_name: str) -> str:
    decomposed = normalize("NFKD", activity_name).encode("ascii", "ignore").decode("ascii").casefold()
    compact = _SLUG_RE.sub("-", decomposed).strip("-")
    if not compact:
        raise RegistryValidationError("annual Orden activity heading has no canonical ASCII identity")
    return compact[:160]


def _unique_active_record_design(
    *,
    sources: Mapping[SourceRefId, SourceReference],
    revision_source_refs: Sequence[SourceRefId],
    filing_year: int,
    period: str,
) -> SourceReference:
    filing_date = period_end_date(filing_year, period)
    candidates = tuple(
        source
        for source in sources.values()
        if source.kind == "record_design"
        and source.id in revision_source_refs
        and source.record_design_epoch is not None
        and source.applies_from is not None
        and source.applies_from <= filing_date
        and (source.applies_to is None or source.applies_to >= filing_date)
    )
    if len(candidates) != 1:
        raise RegistryValidationError(
            f"modelo 303 revision must cite exactly one active record-design source, got {len(candidates)}",
        )
    return candidates[0]


__all__ = [
    "ActividadOrdenAnualRef",
    "M303AnnualOrdenAuthority",
    "M303AnnualOrdenProjection",
    "M303AnnualOrdenRawActivity",
    "M303AnnualOrdenRawModule",
    "M303AnnualOrdenSnapshot",
    "M303AnnualOrdenSourceCensus",
    "M303RegimenSimplificadoSnapshot",
    "check_m303_annual_orden_manifest",
    "collect_m303_annual_orden_fingerprints",
    "compile_m303_annual_orden_projection",
    "extract_m303_annual_orden_source",
    "extract_m303_annual_orden_tables",
    "load_m303_annual_orden_authority",
    "m303_annual_orden_activity_anchor",
    "m303_annual_orden_table_text",
    "render_m303_annual_orden_manifest",
    "resolve_m303_regimen_simplificado_snapshot",
]
