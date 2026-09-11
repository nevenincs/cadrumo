"""Development compiler for mutable registry authoring trees.

This is deliberately outside ``src/``.  It is the only place that turns TOML
sources into registry schema models; shipped runtime reads a signed artifact.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date
from functools import lru_cache
from pathlib import Path

from cadrumo.core.directory_scan import scan_directory
from cadrumo.domain.calculations.registry.errors import RegistryLoadError
from cadrumo.domain.calculations.registry.schema import (
    ModeloDefinition,
    RegistryCatalogues,
    SociedadesAnnualManualCoverageCatalogue,
    SociedadesAnnualManualCoverageStatus,
    SupportedFilingYearsCatalogue,
)
from cadrumo.domain.calculations.registry.schema_references import LegalReference, SourceReference

from ._compiled_cache import (
    load_compiled_registry_cache,
    store_compiled_registry_cache,
)
from ._loader_internals import (
    _collect_modelo_directory_fingerprints,
    _collect_registry_tree_fingerprints,
    _load_catalogue_file_cached,
    _load_modelo_directory_cached,
    _refresh_modelo_directory_fingerprints_after_load_error,
    _refresh_registry_tree_fingerprints_after_load_error,
    _RegistryPathFingerprints,
    _toml_fingerprint,
    _validate_legal_directory,
    load_modelo_file,
)
from .identity import (
    RegistryIdentity,
    resolve_registry_identity,
    stamped_cache_key_tuples,
)
from .loader_cache import (
    ModeloSource,
    discover_modelo_sources,
    is_bundled_registry_root,
    registry_disk_cache_enabled,
    validate_modelo_directory_source,
)
from .loader_fingerprints import (
    refresh_toml_fingerprint_after_load_error as _refresh_toml_fingerprint_after_load_error,
)


def load_modelo_directory(directory: Path) -> ModeloDefinition:
    """Compile one directory-mode modelo from its mutable TOML sources."""
    resolved = directory.resolve()
    if not resolved.is_dir():
        raise RegistryLoadError(f"{resolved}: modelo directory does not exist")
    if not (resolved / "manifest.toml").is_file():
        raise RegistryLoadError(f"{resolved}: missing manifest.toml")
    validate_modelo_directory_source(resolved)
    fingerprints = _collect_modelo_directory_fingerprints(resolved)
    try:
        return _load_modelo_directory_cached(str(resolved), fingerprints)
    except RegistryLoadError as exc:
        refreshed = _refresh_modelo_directory_fingerprints_after_load_error(resolved, exc)
        if refreshed == fingerprints:
            raise
        return _load_modelo_directory_cached(str(resolved), refreshed)


def load_modelo_source(source: ModeloSource) -> ModeloDefinition:
    """Compile one discovered mutable modelo source."""
    return load_modelo_file(source.path) if source.layout == "single_file" else load_modelo_directory(source.path)


def load_catalogue_file(path: Path) -> RegistryCatalogues:
    """Compile one mutable shared catalogue TOML file."""
    resolved = path.resolve()
    fingerprint = _toml_fingerprint(resolved)
    try:
        return _load_catalogue_file_cached(str(resolved), fingerprint[1], fingerprint[2], fingerprint[3])
    except RegistryLoadError as exc:
        refreshed = _refresh_toml_fingerprint_after_load_error(resolved, exc)
        if refreshed == fingerprint:
            raise
        return _load_catalogue_file_cached(str(resolved), refreshed[1], refreshed[2], refreshed[3])


def load_shared_catalogues(root: Path) -> RegistryCatalogues:
    """Compile shared catalogues without compiling modelos."""
    legal_dir = root.resolve() / "legal"
    _validate_legal_directory(legal_dir)
    legal: dict[str, LegalReference] = {}
    sources: dict[str, SourceReference] = {}
    supported_filing_years: SupportedFilingYearsCatalogue | None = None
    sociedades_annual_manual_coverage: SociedadesAnnualManualCoverageCatalogue | None = None
    for path in scan_directory(legal_dir, pattern="*.toml"):
        catalogue = load_catalogue_file(path)
        overlap = (
            set(legal).intersection(catalogue.legal),
            set(sources).intersection(catalogue.sources),
        )
        if any(overlap):
            detail = f"legal={sorted(overlap[0])!r} sources={sorted(overlap[1])!r}"
            raise RegistryLoadError(f"{path}: duplicate catalogue ids {detail}")
        if catalogue.supported_filing_years is not None:
            if supported_filing_years is not None:
                raise RegistryLoadError(
                    f"{path}: supported_filing_years is already declared by another shared catalogue file"
                )
            supported_filing_years = catalogue.supported_filing_years
        if catalogue.sociedades_annual_manual_coverage is not None:
            if sociedades_annual_manual_coverage is not None:
                raise RegistryLoadError(
                    f"{path}: sociedades_annual_manual_coverage is already declared by another shared catalogue file"
                )
            sociedades_annual_manual_coverage = catalogue.sociedades_annual_manual_coverage
        legal.update(catalogue.legal)
        sources.update(catalogue.sources)
    if supported_filing_years is None or sociedades_annual_manual_coverage is None:
        raise RegistryLoadError(f"{legal_dir}: required shared catalogue declaration is missing")
    _validate_sociedades_annual_manual_coverage(sociedades_annual_manual_coverage, supported_filing_years, sources)
    return RegistryCatalogues(
        legal=legal,
        sources=sources,
        supported_filing_years=supported_filing_years,
        sociedades_annual_manual_coverage=sociedades_annual_manual_coverage,
    )


def _validate_sociedades_annual_manual_coverage(
    catalogue: SociedadesAnnualManualCoverageCatalogue,
    supported_filing_years: SupportedFilingYearsCatalogue,
    sources: Mapping[str, SourceReference],
) -> None:
    if tuple(item.year for item in catalogue.dispositions) != supported_filing_years.years:
        raise RegistryLoadError("Sociedades annual manual coverage must declare exactly the supported filing years")
    for disposition in catalogue.dispositions:
        if disposition.status is not SociedadesAnnualManualCoverageStatus.AVAILABLE:
            continue
        source = sources.get(disposition.source_ref or "")
        if source is None or source.kind != "manual_pdf" or source.authority != "aeat":
            raise RegistryLoadError(
                f"Sociedades annual manual coverage year {disposition.year} has no AEAT manual source"
            )
        if source.corpus_path != f"corpus/manuals/sociedades/{disposition.year}/source.pdf":
            raise RegistryLoadError(
                f"Sociedades annual manual coverage year {disposition.year} has an invalid corpus path"
            )
        if source.applies_from != date(disposition.year, 1, 1) or source.applies_to != date(disposition.year, 12, 31):
            raise RegistryLoadError(
                f"Sociedades annual manual coverage year {disposition.year} has an invalid applicability interval"
            )


def load_registry_tree(
    root: Path, *, identity: RegistryIdentity | None = None
) -> tuple[tuple[ModeloDefinition, ...], RegistryCatalogues]:
    """Compile the complete mutable registry tree for development publication."""
    resolved = root.resolve()
    if identity is None:
        identity = resolve_registry_identity(resolved, collect_fingerprints=_collect_registry_tree_fingerprints)
    if identity.is_stamped:
        return _load_registry_tree_cached(str(resolved), stamped_cache_key_tuples(identity))
    _validate_legal_directory(resolved / "legal")
    discover_modelo_sources(resolved / "modelos")
    fingerprints = _collect_registry_tree_fingerprints(resolved)
    try:
        return _load_registry_tree_cached(str(resolved), fingerprints)
    except RegistryLoadError as exc:
        refreshed = _refresh_registry_tree_fingerprints_after_load_error(resolved, exc)
        if refreshed == fingerprints:
            raise
        return _load_registry_tree_cached(str(resolved), refreshed)


@lru_cache(maxsize=32)
def _load_registry_tree_cached(
    root: str, fingerprints: _RegistryPathFingerprints
) -> tuple[tuple[ModeloDefinition, ...], RegistryCatalogues]:
    resolved = Path(root)
    use_disk_cache = registry_disk_cache_enabled(is_bundled=is_bundled_registry_root(resolved))
    if use_disk_cache and (cached := load_compiled_registry_cache(resolved, fingerprints)) is not None:
        return cached
    result = (
        tuple(load_modelo_source(source) for source in discover_modelo_sources(resolved / "modelos")),
        load_shared_catalogues(resolved),
    )
    if use_disk_cache:
        store_compiled_registry_cache(resolved, fingerprints, result)
    return result


collect_registry_tree_fingerprints = _collect_registry_tree_fingerprints
