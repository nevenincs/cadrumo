"""Manifest generation and authority loading for annual Orden registry data."""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from datetime import date
from pathlib import Path
from typing import TYPE_CHECKING

from ....core import Modelo, scan_directory
from ._errors import RegistryLoadError, RegistryValidationError
from ._ids import LegalRefId, SourceRefId
from ._loader_cache import toml_file_fingerprint
from ._m303_orden_census_artefact import (
    M303_ORDEN_CENSUS_ARTEFACT_FILENAME,
    load_m303_annual_orden_censuses,
    render_m303_annual_orden_censuses,
)
from ._m303_orden_constants import EXTRACTOR_VERSION, SUPPORTED_EJERCICIOS
from ._m303_orden_legal import compile_annual_orden_legal_references
from ._m303_orden_projection_compiler import compile_m303_annual_orden_projection
from ._m303_orden_projection_models import (
    M303AnnualOrdenAuthority,
    M303AnnualOrdenCompilation,
    M303AnnualOrdenGeneratedManifest,
    M303AnnualOrdenGeneratedSource,
    M303AnnualOrdenProjection,
)
from ._m303_orden_raw_models import M303AnnualOrdenSourceCensus
from ._m303_orden_source import extract_m303_annual_orden_source
from ._schema_references import LegalReference, SourceReference

if TYPE_CHECKING:
    from ._schema import ModeloDefinition


def generate_m303_annual_orden_manifest(
    *,
    source_root: Path,
    sources: Mapping[SourceRefId, SourceReference],
) -> M303AnnualOrdenGeneratedManifest:
    """Derive the exact source-integrity manifest from the pinned BOE corpus.

    Takes no ``registry_root``, so it always EXTRACTS. That is what the generator
    needs: an artefact regenerated from a shipped copy of itself would agree with
    that copy by construction and could never detect drift.
    """
    return _generate_manifest_with_censuses(source_root=source_root, sources=sources)[0]


def _generate_manifest_with_censuses(
    *,
    source_root: Path,
    sources: Mapping[SourceRefId, SourceReference],
    registry_root: Path | None = None,
) -> tuple[M303AnnualOrdenGeneratedManifest, dict[SourceRefId, M303AnnualOrdenSourceCensus]]:
    """Derive the manifest AND hand back the censuses it was derived from.

    Extracting one annual Orden means a full BeautifulSoup parse of its BOE
    HTML, so a caller that needs both the manifest row and the census behind it
    should take both from one pass rather than extracting twice.

    ``registry_root`` opts into the build-generated census artefact: when it is
    supplied and the artefact validates against the pinned sources, the censuses
    are read rather than extracted, and the manifest is rebuilt from them. The
    staleness comparison downstream is unaffected and still runs — it simply
    stops costing a BOE parse. Omitted (the generator's own path), every census
    is extracted afresh, which is what makes the generator able to detect drift
    at all.
    """
    generated_sources: list[M303AnnualOrdenGeneratedSource] = []
    censuses: dict[SourceRefId, M303AnnualOrdenSourceCensus] = {}
    shipped = load_m303_annual_orden_censuses(registry_root, sources=sources) if registry_root is not None else None
    for ejercicio in SUPPORTED_EJERCICIOS:
        source = _single_annual_orden_source_for_year(sources, ejercicio=ejercicio)
        census = None if shipped is None else shipped.get(source.id)
        if census is None or census.ejercicio != ejercicio:
            census = extract_m303_annual_orden_source(
                ejercicio=ejercicio,
                source=source,
                source_root=source_root,
            )
        censuses[source.id] = census
        generated_sources.append(_generated_source_from_census(census, ejercicio=ejercicio, source_ref=source.id))
    manifest = M303AnnualOrdenGeneratedManifest(
        extractor_version=EXTRACTOR_VERSION,
        sources=tuple(generated_sources),
    )
    return manifest, censuses


def _generated_source_from_census(
    census: M303AnnualOrdenSourceCensus,
    *,
    ejercicio: int,
    source_ref: SourceRefId,
) -> M303AnnualOrdenGeneratedSource:
    """Project one census into the manifest row it implies.

    Pure, and named rather than inlined, because it is what makes the shipped
    census artefact sufficient: every field of the committed manifest is derived
    from the census, so a runtime holding the censuses can rebuild the manifest
    and re-run the staleness comparison WITHOUT parsing any BOE HTML. The
    comparison therefore stays at runtime and costs microseconds, instead of
    being traded away for the speed.

    Returns:
        The generated manifest row for ``census``.
    """
    return M303AnnualOrdenGeneratedSource(
        ejercicio=ejercicio,
        source_ref=source_ref,
        source_content_digest=census.source_content_digest,
        activity_table_count=len(census.activities),
        module_row_count=sum(len(activity.modules) for activity in census.activities),
        module_distribution=tuple(
            sum(len(activity.modules) == size for activity in census.activities) for size in range(1, 8)
        ),
        agricultural_index_row_count=len(census.agricultural_indexes),
        agricultural_ingreso_a_cuenta_row_count=len(census.agricultural_ingresos_a_cuenta),
        non_agricultural_ingreso_a_cuenta_row_count=len(census.non_agricultural_ingresos_a_cuenta),
        seasonal_index_day_bands=tuple((item.minimum_days, item.maximum_days) for item in census.seasonal_indexes),
        seasonal_index_coefficients=tuple(item.coefficient for item in census.seasonal_indexes),
        difficult_justification_pct=census.difficult_justification.percentage,
        lorca_2022_reduction_pct=(
            None if census.lorca_2022_reduction is None else census.lorca_2022_reduction.percentage
        ),
    )


def render_m303_annual_orden_manifest(
    *,
    source_root: Path,
    sources: Mapping[SourceRefId, SourceReference],
) -> str:
    """Render the generated registry artefact in canonical TOML order."""
    return _render_generated_manifest(
        generate_m303_annual_orden_manifest(source_root=source_root, sources=sources),
    )


def render_m303_annual_orden_census_artefact(
    *,
    source_root: Path,
    sources: Mapping[SourceRefId, SourceReference],
) -> str:
    """Extract every pinned annual Orden and render the committed census artefact.

    Lives here rather than beside the artefact's other serialisation because it
    is the one direction that needs the EXTRACTOR, and the artefact module is
    deliberately free of that import edge. The rendering itself still belongs to
    the artefact module, so there remains exactly one place that decides what the
    committed bytes look like.

    Returns:
        The artefact text, exactly as the generator commits it.
    """
    _manifest, censuses = _generate_manifest_with_censuses(source_root=source_root, sources=sources)
    return render_m303_annual_orden_censuses(tuple(censuses[key] for key in sorted(censuses)))


def check_m303_annual_orden_census_artefact(
    *,
    artefact_path: Path,
    source_root: Path,
    sources: Mapping[SourceRefId, SourceReference],
) -> None:
    """Refuse a missing, hand-edited, or stale committed census artefact.

    The build-side half of the annual-Orden proof. It re-extracts from the pinned
    BOE corpus and compares against the committed bytes, so it is the only thing
    standing between a stale census and every runtime that now trusts one. The
    runtime cannot perform this check itself without paying the parse this
    artefact exists to remove, which is exactly why it is a build and
    continuous-integration gate.

    Raises:
        RegistryLoadError: When the artefact is absent, unreadable, or does not
            equal a fresh extraction.
    """
    if not artefact_path.is_file():
        raise RegistryLoadError(f"annual Orden census artefact is missing: {artefact_path}")
    expected = render_m303_annual_orden_census_artefact(source_root=source_root, sources=sources)
    try:
        actual = artefact_path.read_text(encoding="utf-8")
    except OSError as exc:
        raise RegistryLoadError(f"annual Orden census artefact cannot be read: {artefact_path}") from exc
    if actual != expected:
        raise RegistryLoadError(f"annual Orden census artefact is stale: regenerate {artefact_path}")


def _render_generated_manifest(manifest: M303AnnualOrdenGeneratedManifest) -> str:
    """Render an ALREADY-generated manifest in canonical TOML order.

    Split out because generating the manifest costs a full BeautifulSoup pass
    over every pinned annual Orden and the staleness check needs both the
    rendered text and the manifest object. Rendering from the object it was
    handed lets that caller derive both from one generation.
    """
    lines = [
        "# Generated by the registry authoring tooling; do not edit by hand.",
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
                f"agricultural_index_row_count = {source.agricultural_index_row_count}",
                f"agricultural_ingreso_a_cuenta_row_count = {source.agricultural_ingreso_a_cuenta_row_count}",
                f"non_agricultural_ingreso_a_cuenta_row_count = {source.non_agricultural_ingreso_a_cuenta_row_count}",
                "seasonal_index_day_bands = ["
                + ", ".join(f"[{start}, {end}]" for start, end in source.seasonal_index_day_bands)
                + "]",
                "seasonal_index_coefficients = ["
                + ", ".join(f'"{value}"' for value in source.seasonal_index_coefficients)
                + "]",
                f'difficult_justification_pct = "{source.difficult_justification_pct}"',
                *(
                    ()
                    if source.lorca_2022_reduction_pct is None
                    else (f'lorca_2022_reduction_pct = "{source.lorca_2022_reduction_pct}"',)
                ),
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
    return _check_manifest_with_censuses(
        manifest_path=manifest_path,
        source_root=source_root,
        sources=sources,
    )[0]


def _check_manifest_with_censuses(
    *,
    manifest_path: Path,
    source_root: Path,
    sources: Mapping[SourceRefId, SourceReference],
    registry_root: Path | None = None,
) -> tuple[M303AnnualOrdenGeneratedManifest, dict[SourceRefId, M303AnnualOrdenSourceCensus]]:
    """Run the staleness refusal and hand back the censuses behind it.

    ``registry_root`` lets the censuses come from the build-generated artefact
    instead of a BOE parse. The refusal is identical either way: the manifest is
    rebuilt from whichever censuses were obtained and its rendered text compared
    against the committed bytes. What changes is only the cost of obtaining them.
    """
    try:
        directory_entries = scan_directory(manifest_path.parent, require_root=True)
    except OSError as exc:
        raise RegistryLoadError(f"annual Orden generated directory cannot be read: {manifest_path.parent}") from exc
    # The generated directory admits exactly the artefacts the generator writes.
    # The census artefact is named through its owning module rather than spelled
    # here, so a rename there cannot leave this guard refusing the very file the
    # build produces.
    generated_names = frozenset({manifest_path.name, M303_ORDEN_CENSUS_ARTEFACT_FILENAME})
    unexpected_entries = tuple(entry for entry in directory_entries if entry.name not in generated_names)
    if unexpected_entries:
        names = ", ".join(sorted(entry.name for entry in unexpected_entries))
        raise RegistryLoadError(f"annual Orden generated directory contains unexpected entries: {names}")
    if not manifest_path.is_file():
        raise RegistryLoadError(f"annual Orden generated manifest is missing: {manifest_path}")
    # Generated ONCE and used twice. The comparison text and the returned
    # manifest are the same derivation of the same corpus, so deriving them
    # separately cost a second full extraction of every pinned annual Orden
    # and could not have disagreed.
    manifest, censuses = _generate_manifest_with_censuses(
        source_root=source_root,
        sources=sources,
        registry_root=registry_root,
    )
    expected = _render_generated_manifest(manifest)
    try:
        actual = manifest_path.read_text(encoding="utf-8")
    except OSError as exc:
        raise RegistryLoadError(f"annual Orden generated manifest cannot be read: {manifest_path}") from exc
    if actual != expected:
        raise RegistryLoadError(f"annual Orden generated manifest is stale: regenerate {manifest_path}")
    return manifest, censuses


def load_m303_annual_orden_authority(
    root: Path,
    *,
    source_root: Path,
    modelos: Sequence[ModeloDefinition],
    sources: Mapping[SourceRefId, SourceReference],
) -> M303AnnualOrdenCompilation:
    """Compile source-pinned annual Orden rows and legal provisions into the registry."""
    manifest_path = root.resolve() / "m303_orden_anual" / "manifest.toml"
    # The staleness check already extracted every pinned Orden to build the
    # manifest it compared against disk. Those censuses are exactly what the
    # compile below needs, so they are carried out of the check rather than
    # re-derived: extracting one Orden is a full BeautifulSoup parse of its BOE
    # HTML, and this loop used to pay for all five a second time.
    manifest, censuses = _check_manifest_with_censuses(
        manifest_path=manifest_path,
        source_root=source_root,
        sources=sources,
        registry_root=root.resolve(),
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
            census=censuses.get(generated_source.source_ref),
        )
        _merge_annual_orden_legal_refs(legal, table_legal_refs.values())
        projections.extend(
            _annual_orden_projections_for_source(
                census=census,
                source=source,
                modelo_303=modelo_303,
                sources=sources,
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
    census: M303AnnualOrdenSourceCensus | None = None,
) -> tuple[SourceReference, M303AnnualOrdenSourceCensus, dict[str, LegalReference]]:
    """Compile one pinned annual Orden, extracting it only if not already done.

    ``census`` is the extraction the manifest check already performed for this
    source. It is the same pure derivation of the same bytes this function would
    otherwise recompute, so accepting it changes no value; it only stops the
    corpus being parsed a second time.
    """
    source = sources.get(generated_source.source_ref)
    if source is None:
        raise RegistryLoadError(f"annual Orden manifest names unknown source {generated_source.source_ref!r}")
    if census is None:
        census = extract_m303_annual_orden_source(
            ejercicio=generated_source.ejercicio,
            source=source,
            source_root=source_root,
        )
    _validate_generated_source_matches_census(generated_source, census)
    legal_refs = compile_annual_orden_legal_references(census, source=source)
    return source, census, legal_refs


def _annual_orden_projections_for_source(
    *,
    census: M303AnnualOrdenSourceCensus,
    source: SourceReference,
    modelo_303: ModeloDefinition,
    sources: Mapping[SourceRefId, SourceReference],
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
        record_design_source = _annual_orden_record_design_source(revision.source_refs, sources=sources)
        projections.append(
            compile_m303_annual_orden_projection(
                census=census,
                registry_revision_id=revision.id,
                record_design_source_ref=record_design_source.id,
                record_design_source_content_digest=record_design_source.sha256,
                legal_refs={identity: legal_ref.id for identity, legal_ref in table_legal_refs.items()},
            ),
        )
    return tuple(projections)


def _annual_orden_record_design_source(
    revision_source_refs: Sequence[SourceRefId],
    *,
    sources: Mapping[SourceRefId, SourceReference],
) -> SourceReference:
    candidates = tuple(
        source
        for source_ref in revision_source_refs
        if (source := sources.get(source_ref)) is not None
        and source.kind == "record_design"
        and source.record_design_epoch is not None
    )
    if len(candidates) != 1:
        raise RegistryValidationError(
            "Modelo 303 annual Orden projection requires exactly one revision-owned record-design source",
        )
    return candidates[0]


def _merge_annual_orden_legal_refs(
    legal: dict[LegalRefId, LegalReference],
    generated_refs: Iterable[LegalReference],
) -> None:
    for legal_ref in generated_refs:
        if legal_ref.id in legal:
            raise RegistryValidationError(f"annual Orden compiler generated duplicate legal ref {legal_ref.id!r}")
        legal[legal_ref.id] = legal_ref


def collect_m303_annual_orden_fingerprints(root: Path) -> tuple[tuple[str, int, int, str], ...]:
    """Fingerprint every generated annual-Orden artefact and no hand-authored rows.

    Deliberately NOT ``pattern="*.toml"``. The generated directory carries the
    invariants manifest as TOML and the census artefact as JSON, and a TOML-only
    glob would leave the census outside the cache key entirely -- so an edit to
    it would be served from a compiled cache that still looked valid. Both files
    are generated by the same tool from the same corpus and both must move the
    key.
    """
    directory = root.resolve() / "m303_orden_anual"
    return tuple(toml_file_fingerprint(path.resolve()) for path in scan_directory(directory))


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
    if generated.source_ref != census.source_ref or generated.source_content_digest != census.source_content_digest:
        raise RegistryValidationError("annual Orden generated source no longer matches its pinned source identity")
    _validate_generated_source_activity_counts(generated, census)
    _validate_generated_source_axis_counts(generated, census)


def _validate_generated_source_activity_counts(
    generated: M303AnnualOrdenGeneratedSource,
    census: M303AnnualOrdenSourceCensus,
) -> None:
    actual_distribution = tuple(
        sum(len(activity.modules) == size for activity in census.activities) for size in range(1, 8)
    )
    if generated.activity_table_count != len(census.activities):
        raise RegistryValidationError("annual Orden generated source activity count no longer matches the BOE HTML")
    if generated.module_row_count != sum(len(activity.modules) for activity in census.activities):
        raise RegistryValidationError("annual Orden generated source module count no longer matches the BOE HTML")
    if generated.module_distribution != actual_distribution:
        raise RegistryValidationError(
            "annual Orden generated source module distribution no longer matches the BOE HTML",
        )


def _validate_generated_source_axis_counts(
    generated: M303AnnualOrdenGeneratedSource,
    census: M303AnnualOrdenSourceCensus,
) -> None:
    _validate_generated_source_agricultural_axis_counts(generated, census)
    _validate_generated_source_non_agricultural_axis_count(generated, census)
    _validate_generated_source_seasonal_axis(generated, census)
    _validate_generated_source_difficult_justification(generated, census)
    _validate_generated_source_lorca_reduction(generated, census)


def _validate_generated_source_agricultural_axis_counts(
    generated: M303AnnualOrdenGeneratedSource,
    census: M303AnnualOrdenSourceCensus,
) -> None:
    if generated.agricultural_index_row_count != len(census.agricultural_indexes):
        raise RegistryValidationError(
            "annual Orden generated source agricultural-index count no longer matches the BOE HTML"
        )
    if generated.agricultural_ingreso_a_cuenta_row_count != len(census.agricultural_ingresos_a_cuenta):
        raise RegistryValidationError(
            "annual Orden generated source agricultural ingreso-a-cuenta count no longer matches the BOE HTML",
        )


def _validate_generated_source_non_agricultural_axis_count(
    generated: M303AnnualOrdenGeneratedSource,
    census: M303AnnualOrdenSourceCensus,
) -> None:
    if generated.non_agricultural_ingreso_a_cuenta_row_count != len(census.non_agricultural_ingresos_a_cuenta):
        raise RegistryValidationError(
            "annual Orden generated source IAE ingreso-a-cuenta count no longer matches the BOE HTML",
        )


def _validate_generated_source_seasonal_axis(
    generated: M303AnnualOrdenGeneratedSource,
    census: M303AnnualOrdenSourceCensus,
) -> None:
    actual_bands = tuple((item.minimum_days, item.maximum_days) for item in census.seasonal_indexes)
    actual_coefficients = tuple(item.coefficient for item in census.seasonal_indexes)
    if (
        generated.seasonal_index_day_bands != actual_bands
        or generated.seasonal_index_coefficients != actual_coefficients
    ):
        raise RegistryValidationError("annual Orden generated source seasonal indexes no longer match the BOE HTML")


def _validate_generated_source_difficult_justification(
    generated: M303AnnualOrdenGeneratedSource,
    census: M303AnnualOrdenSourceCensus,
) -> None:
    if generated.difficult_justification_pct != census.difficult_justification.percentage:
        raise RegistryValidationError(
            "annual Orden generated source difficult-justification percentage no longer matches the BOE HTML",
        )


def _validate_generated_source_lorca_reduction(
    generated: M303AnnualOrdenGeneratedSource,
    census: M303AnnualOrdenSourceCensus,
) -> None:
    actual_percentage = None if census.lorca_2022_reduction is None else census.lorca_2022_reduction.percentage
    if generated.lorca_2022_reduction_pct != actual_percentage:
        raise RegistryValidationError(
            "annual Orden generated source Lorca 2022 reduction no longer matches the BOE HTML",
        )
