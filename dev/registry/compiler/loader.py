"""Development compiler for mutable registry authoring trees.

This is deliberately outside ``src/``.  It is the only place that turns TOML
sources into registry schema models; shipped runtime reads a published, digest-checked artifact.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date
from functools import lru_cache
from pathlib import Path

from cadrumo.core.directory_scan import scan_directory
from cadrumo.domain.calculations.registry.errors import RegistryLoadError
from cadrumo.domain.calculations.registry.modelo_localization import (
    ModeloLocalizationFieldKind,
    casilla_alias_locale_key,
    casilla_continuity_locale_key,
    casilla_occurrence_locale_key,
    construct_locale_key,
    modelo_locale_key,
    revision_locale_key,
)
from cadrumo.domain.calculations.registry.schema import (
    ModeloDefinition,
    RegistryCatalogues,
    SociedadesAnnualManualCoverageCatalogue,
    SociedadesAnnualManualCoverageStatus,
    SupportedFilingYearsCatalogue,
)
from cadrumo.domain.calculations.registry.schema_references import LegalReference, SourceReference

from ._loader_internals import (
    _load_catalogue_file_cached,
    _load_modelo_directory_cached,
    _load_modelo_manifest,
    _load_modelo_revisions,
    _materialise_revisions,
    _refresh_modelo_directory_fingerprints_after_load_error,
    _refresh_registry_tree_fingerprints_after_load_error,
    _RegistryPathFingerprints,
    _toml_fingerprint,
    _validate_legal_directory,
)
from .compiled_cache import (
    load_compiled_registry_cache,
    store_compiled_registry_cache,
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
    collect_modelo_directory_fingerprints,
    collect_registry_tree_fingerprints,
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
    fingerprints = collect_modelo_directory_fingerprints(resolved)
    try:
        return _load_modelo_directory_cached(str(resolved), fingerprints)
    except RegistryLoadError as exc:
        refreshed = _refresh_modelo_directory_fingerprints_after_load_error(resolved, exc)
        if refreshed == fingerprints:
            raise
        return _load_modelo_directory_cached(str(resolved), refreshed)


def load_modelo_source(source: ModeloSource) -> ModeloDefinition:
    """Compile one discovered mutable modelo source."""
    return load_modelo_directory(source.path)


def load_modelo_locale_key_projection(root: Path) -> frozenset[str]:
    """Read the committed Modelo structure and derive its locale-key universe.

    Locale inventory must remain available while the binding provider schema is
    being migrated (or when an unrelated binding row is malformed).  This
    projection therefore stops at the structural compiler boundary: it reads
    manifests and revision fragments, materialises only the casilla predecessor
    chain, and validates the identity-bearing arrays needed for localization.
    It never constructs a typed ``BindingDefinition`` or reads the shared
    catalogue, so binding validation cannot erase the Modelo key universe.

    The projection is deliberately strict about localization structure.  A
    malformed or ambiguous modelo, revision, construct, casilla, or alias row
    raises ``RegistryLoadError`` rather than returning a partial key set.
    """
    resolved = root.resolve()
    sources = discover_modelo_sources(resolved / "modelos")
    if not sources:
        raise RegistryLoadError(f"{resolved / 'modelos'}: no modelo sources found")

    keys: set[str] = set()
    for source in sources:
        manifest = _load_modelo_manifest(source.path)
        modelo_table = _raw_table(manifest.get("modelo"))
        if modelo_table is None:
            raise RegistryLoadError(f"{source.manifest_path}: missing [modelo] table")
        modelo_id = _required_identity(modelo_table.get("id"), f"{source.manifest_path}: [modelo].id")
        revisions = _load_modelo_revisions(source.path)
        if not revisions:
            raise RegistryLoadError(f"{source.path}: no revisions found in revisions/")
        _validate_predecessor_references(source.path, revisions)
        materialised = _materialise_revisions(source.path, modelo_id, revisions).revisions

        keys.add(modelo_locale_key(modelo_id, "title"))
        keys.add(modelo_locale_key(modelo_id, "official_name"))
        for revision_id, raw_revision in materialised.items():
            revision_token = _required_identity(revision_id, f"{source.path}: revision id")
            revision_table = _raw_table(raw_revision)
            if revision_table is None:
                raise RegistryLoadError(f"{source.path}: revision {revision_token!r} must be a table")
            authored_revision_id = revision_table.get("id")
            if authored_revision_id is not None and authored_revision_id != revision_token:
                raise RegistryLoadError(
                    f"{source.path}: revision {revision_token!r} authored id {authored_revision_id!r} differs",
                )
            keys.add(revision_locale_key(modelo_id, revision_token))
            _project_revision_locale_keys(keys, modelo_id, revision_token, revision_table, source.path)
    return frozenset(keys)


def _raw_table(value: object) -> Mapping[str, object] | None:
    """Return a TOML table without coercing malformed values."""
    return value if isinstance(value, Mapping) else None


def _required_identity(value: object, subject: str) -> str:
    """Require one non-blank string identity used in a locale key."""
    if not isinstance(value, str) or not value.strip():
        raise RegistryLoadError(f"{subject} must be a non-blank string")
    return value


def _raw_array(table: Mapping[str, object], field: str, subject: str) -> tuple[object, ...]:
    """Read one optional TOML array, treating absence as the schema default."""
    value = table.get(field, ())
    if not isinstance(value, tuple):
        raise RegistryLoadError(f"{subject}: {field!r} must be an array")
    return value


def _validate_predecessor_references(source_path: Path, revisions: Mapping[str, object]) -> None:
    """Reject predecessor shapes that would make inherited locale rows unknowable."""
    revision_ids = set(revisions)
    for revision_id, raw_revision in revisions.items():
        table = _raw_table(raw_revision)
        if table is None:
            raise RegistryLoadError(f"{source_path}: revision {revision_id!r} must be a table")
        predecessor = table.get("predecessor")
        if predecessor is None:
            continue
        if isinstance(predecessor, str):
            if predecessor not in revision_ids:
                raise RegistryLoadError(
                    f"{source_path}: revision {revision_id!r} declares unknown predecessor {predecessor!r}",
                )
            continue
        if isinstance(predecessor, Mapping) and set(predecessor) == {"none"}:
            continue
        raise RegistryLoadError(
            f"{source_path}: revision {revision_id!r} predecessor must name a sibling or declare none",
        )


def _project_revision_locale_keys(
    keys: set[str],
    modelo_id: str,
    revision_id: str,
    revision: Mapping[str, object],
    source_path: Path,
) -> None:
    """Project construct, casilla, and alias identities from one raw revision."""
    constructs = _raw_array(revision, "constructs", f"{source_path}: revision {revision_id!r}")
    seen_construct_ids: set[str] = set()
    for index, raw_construct in enumerate(constructs):
        subject = f"{source_path}: revision {revision_id!r} construct[{index}]"
        construct = _raw_table(raw_construct)
        if construct is None:
            raise RegistryLoadError(f"{subject} must be a table")
        construct_id = _required_identity(construct.get("id"), f"{subject}.id")
        if construct_id in seen_construct_ids:
            raise RegistryLoadError(f"{subject}: duplicate construct id {construct_id!r}")
        seen_construct_ids.add(construct_id)
        keys.add(construct_locale_key(modelo_id, revision_id, construct_id))

    casillas = _raw_array(revision, "casillas", f"{source_path}: revision {revision_id!r}")
    seen_casilla_ids: set[str] = set()
    for index, raw_casilla in enumerate(casillas):
        subject = f"{source_path}: revision {revision_id!r} casilla[{index}]"
        casilla = _raw_table(raw_casilla)
        if casilla is None:
            raise RegistryLoadError(f"{subject} must be a table")
        casilla_id = _required_identity(casilla.get("id"), f"{subject}.id")
        if casilla_id in seen_casilla_ids:
            raise RegistryLoadError(f"{subject}: duplicate casilla id {casilla_id!r}")
        seen_casilla_ids.add(casilla_id)

        localization_keys = [
            casilla_occurrence_locale_key(modelo_id, revision_id, casilla_id, ModeloLocalizationFieldKind.LABEL),
        ]
        if "continuidad_id" in casilla:
            continuidad_id = _required_identity(casilla["continuidad_id"], f"{subject}.continuidad_id")
            localization_keys.append(
                casilla_continuity_locale_key(modelo_id, continuidad_id, ModeloLocalizationFieldKind.LABEL),
            )
        for localization_key in localization_keys:
            keys.add(localization_key)
            keys.add(f"{localization_key.removesuffix('.label')}.help")

        aliases = _raw_array(casilla, "aliases", subject)
        for alias_index, raw_alias in enumerate(aliases):
            if _raw_table(raw_alias) is None:
                raise RegistryLoadError(f"{subject} alias[{alias_index}] must be a table")
            keys.add(casilla_alias_locale_key(modelo_id, revision_id, casilla_id, str(alias_index)))


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
        identity = resolve_registry_identity(resolved, collect_fingerprints=collect_registry_tree_fingerprints)
    if identity.is_stamped:
        return load_registry_tree_cached(str(resolved), stamped_cache_key_tuples(identity))
    _validate_legal_directory(resolved / "legal")
    discover_modelo_sources(resolved / "modelos")
    fingerprints = collect_registry_tree_fingerprints(resolved)
    try:
        return load_registry_tree_cached(str(resolved), fingerprints)
    except RegistryLoadError as exc:
        refreshed = _refresh_registry_tree_fingerprints_after_load_error(resolved, exc)
        if refreshed == fingerprints:
            raise
        return load_registry_tree_cached(str(resolved), refreshed)


@lru_cache(maxsize=32)
def load_registry_tree_cached(
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


def clear_registry_tree_cache() -> None:
    """Clear the in-process compiled-tree memo without touching disk caches."""
    load_registry_tree_cached.cache_clear()
