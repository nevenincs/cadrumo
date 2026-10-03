"""Development-only mutable-registry TOML directory loading and cache management."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import BaseModel, ValidationError

from cadrumo.core.directory_scan import (
    DirectoryEntryKind,
    scan_directory,
)
from cadrumo.core.toml import freeze_toml, read_toml
from cadrumo.domain.calculations.registry.errors import (
    RegistryFailureClassification,
    RegistryFailureCondition,
    RegistryLoadError,
)
from cadrumo.domain.calculations.registry.schema import (
    REVISION_GOVERNANCE_FIELDS as _REVISION_GOVERNANCE_FIELDS,
)
from cadrumo.domain.calculations.registry.schema import (
    REVISION_MANIFEST_ONLY_FIELDS as _REVISION_MANIFEST_ONLY_FIELDS,
)
from cadrumo.domain.calculations.registry.schema import (
    ModeloDefinition,
    RegistryCatalogues,
    SociedadesAnnualManualCoverageCatalogue,
    SupportedFilingYearsCatalogue,
)
from cadrumo.domain.calculations.registry.schema_references import LegalReference, SourceReference

from ._loader_revision_fragments import (
    merge_revision_fragment as _merge_revision_fragment,
)
from ._loader_revision_fragments import (
    merge_revision_manifest as _merge_revision_manifest,
)
from ._toml_helpers import as_toml_table as _as_toml_table
from .loader_cache import (
    ModeloRevisionSource as _ModeloRevisionSource,
)
from .loader_cache import (
    toml_file_fingerprint,
)
from .loader_fingerprints import (
    clear_fingerprint_cache as _clear_fingerprint_cache,
)
from .loader_fingerprints import (
    collect_modelo_directory_fingerprints,
    collect_registry_tree_fingerprints,
)
from .loader_grammar import revision_section_fragment_paths
from .revision_definition import _build_modelo_definition_from_data

ModeloRevisionSource = _ModeloRevisionSource


clear_fingerprint_cache = _clear_fingerprint_cache


REVISION_GOVERNANCE_FIELDS = _REVISION_GOVERNANCE_FIELDS


REVISION_MANIFEST_ONLY_FIELDS = _REVISION_MANIFEST_ONLY_FIELDS


type _RegistryPathFingerprint = tuple[str, int, int, str]


type _RegistryPathFingerprints = tuple[_RegistryPathFingerprint, ...]


@lru_cache(maxsize=64)
def _load_modelo_directory_cached(
    directory: str,
    fingerprints: _RegistryPathFingerprints,
    tax_id_format: object | None = None,
) -> ModeloDefinition:
    del fingerprints
    resolved = Path(directory)
    manifest_data = _load_modelo_manifest(resolved)
    merged_revisions = _load_modelo_revisions(resolved)
    if not merged_revisions:
        raise RegistryLoadError(f"{resolved}: no revisions found in revisions/")
    merged: dict[str, object] = {**manifest_data, "revisions": merged_revisions}
    validation_context = None
    if tax_id_format is not None:
        from cadrumo.core.identity.documents import TAX_ID_FORMAT_CONTEXT

        validation_context = {TAX_ID_FORMAT_CONTEXT: tax_id_format}
    return _build_modelo_definition_from_data(resolved, merged, validation_context=validation_context)


def _load_modelo_manifest(resolved: Path) -> dict[str, object]:
    """Load the directory-mode manifest.toml and reject inlined [revisions]."""
    manifest_path = resolved / "manifest.toml"
    manifest_data = freeze_toml(read_toml(manifest_path, error_factory=RegistryLoadError))
    if "revisions" in manifest_data:
        raise RegistryLoadError(
            f"{manifest_path}: directory-mode manifest must not declare [revisions]; "
            "revision data lives in revisions/<id>/revision.toml",
        )
    return manifest_data


def _load_modelo_revisions(resolved: Path) -> dict[str, object]:
    """Merge every ``revisions/<id>/`` fragment directory into one ``{revision_id: raw}`` map.

    A missing ``revisions/`` directory returns an empty dict; the caller raises
    if no revisions land. Each revision directory contributes its
    ``revision.toml`` metadata plus its section fragments under the directory's
    own id.
    """
    revisions_dir = resolved / "revisions"
    if not revisions_dir.is_dir():
        return {}
    merged_revisions: dict[str, object] = {}
    for path in scan_directory(revisions_dir, select=DirectoryEntryKind.FILES):
        raise RegistryLoadError(
            f"{path}: revision files are not a supported layout; "
            "each revision must be a revisions/<id>/ directory containing revision.toml",
        )
    for path in scan_directory(revisions_dir, select=DirectoryEntryKind.DIRECTORIES):
        _merge_revision_directory(path, merged_revisions)
    return merged_revisions


def _merge_revision_directory(path: Path, merged_revisions: dict[str, object]) -> None:
    """Merge a ``revisions/{id}/`` fragment tree into ``merged_revisions``."""
    revision_id = path.name
    if revision_id in merged_revisions:
        raise RegistryLoadError(f"{path}: revision {revision_id!r} is declared more than once")
    revision_manifest = path / "revision.toml"
    if not revision_manifest.is_file():
        raise RegistryLoadError(f"{path}: revision fragment directory must contain revision.toml")
    section_fragments = revision_section_fragment_paths(_revision_section_directories(path))
    merged_revision: dict[str, object] = {}
    _merge_revision_manifest(revision_manifest, revision_id, merged_revision)
    for fragment_path in section_fragments:
        _merge_revision_fragment(fragment_path, revision_id, merged_revision)
    merged_revisions[revision_id] = merged_revision


def _revision_section_directories(path: Path) -> tuple[Path, ...]:
    # require_root: the caller has already resolved this revision fragment
    # directory and read its revision.toml, so an unreadable path here is a
    # broken tree, not an empty revision. Silently returning no sections would
    # compile a revision with none of its casillas.
    return tuple(
        entry
        for entry in scan_directory(path, select=DirectoryEntryKind.DIRECTORIES, require_root=True)
        if entry.name != "locales"
    )


@lru_cache(maxsize=128)
def _load_catalogue_file_cached(
    path: str,
    byte_count: int,
    modified_ns: int,
    content_digest: str,
) -> RegistryCatalogues:
    del byte_count, modified_ns, content_digest
    source_path = Path(path)
    data = freeze_toml(read_toml(source_path, error_factory=RegistryLoadError))
    if "parameters" in data:
        raise RegistryLoadError(
            f"{source_path}: retired global [parameters] catalogue section is forbidden; "
            "author a governed fact instead",
        )
    legal = _validate_catalogue_section(
        source_path,
        raw=data.get("legal"),
        kind="legal reference",
        model=LegalReference,
    )
    sources = _validate_catalogue_section(
        source_path,
        raw=data.get("sources") or data.get("source"),
        kind="source reference",
        model=SourceReference,
    )
    supported_filing_years = None
    raw_supported_filing_years = data.get("supported_filing_years")
    if raw_supported_filing_years is not None:
        try:
            supported_filing_years = SupportedFilingYearsCatalogue.model_validate(raw_supported_filing_years)
        except ValidationError as exc:
            raise RegistryLoadError(f"{source_path}: invalid supported_filing_years catalogue: {exc}") from exc
    sociedades_annual_manual_coverage = None
    raw_sociedades_annual_manual_coverage = data.get("sociedades_annual_manual_coverage")
    if raw_sociedades_annual_manual_coverage is not None:
        try:
            sociedades_annual_manual_coverage = SociedadesAnnualManualCoverageCatalogue.model_validate(
                raw_sociedades_annual_manual_coverage,
            )
        except ValidationError as exc:
            raise RegistryLoadError(
                f"{source_path}: invalid sociedades_annual_manual_coverage catalogue: {exc}",
            ) from exc
    return RegistryCatalogues(
        legal=legal,
        sources=sources,
        supported_filing_years=supported_filing_years,
        sociedades_annual_manual_coverage=sociedades_annual_manual_coverage,
    )


def _validate_catalogue_section[T: BaseModel](
    source_path: Path,
    *,
    raw: object,
    kind: str,
    model: type[T],
) -> dict[str, T]:
    """Validate one ``{id: payload}`` section of a catalogue TOML into typed records.

    Returns an empty dict when ``raw`` is not a dict (the section is
    absent or malformed at the top level — the absent case is
    legitimate for catalogues that don't declare every section).
    Each ``(id, payload)`` pair is fed through ``model.model_validate``
    with ``id`` injected; type-shape errors raise the typed
    ``RegistryLoadError`` envelope so the catalogue loader's failure
    mode stays uniform across the legal and source sections.
    """
    table = _as_toml_table(raw)
    if table is None:
        return {}
    out: dict[str, T] = {}
    for ref_id, payload in table.items():
        payload_table = _as_toml_table(payload)
        if payload_table is None:
            raise RegistryLoadError(f"{source_path}: malformed {kind} entry")
        try:
            out[ref_id] = model.model_validate({"id": ref_id, **payload_table})
        except ValidationError as exc:
            raise RegistryLoadError(f"{source_path}: invalid {kind} {ref_id!r}: {exc}") from exc
    return out


def _validate_legal_directory(legal_dir: Path) -> None:
    """Require the shared legal catalogue to remain one flat TOML directory."""
    if not legal_dir.is_dir():
        return
    for entry in scan_directory(legal_dir):
        if entry.is_dir():
            raise RegistryLoadError(f"{entry}: unrecognized legal directory; legal catalogues must be flat")
        if not entry.is_file() or entry.suffix != ".toml":
            raise RegistryLoadError(
                f"{entry}: unrecognized legal catalogue file; legal catalogues must use the '.toml' suffix",
            )


def _refresh_modelo_directory_fingerprints_after_load_error(
    resolved: Path,
    initial_error: RegistryLoadError,
) -> _RegistryPathFingerprints:
    try:
        return collect_modelo_directory_fingerprints(resolved)
    except RegistryLoadError as refresh_error:
        raise RegistryLoadError(
            f"{resolved}: modelo directory changed during load. "
            f"Initial failure: {initial_error}; refresh failure: {refresh_error}",
            registry_failure=RegistryFailureClassification(
                condition=RegistryFailureCondition.TREE_QUIESCENT,
                facts={
                    "path": str(resolved),
                    "registry_tree_quiescent": False,
                    "operation": "modelo_directory_refresh",
                },
            ),
        ) from refresh_error


def _refresh_registry_tree_fingerprints_after_load_error(
    resolved: Path,
    initial_error: RegistryLoadError,
) -> _RegistryPathFingerprints:
    try:
        return collect_registry_tree_fingerprints(resolved, use_cache=False)
    except RegistryLoadError as refresh_error:
        raise RegistryLoadError(
            f"{resolved}: registry tree changed during load. "
            f"Initial failure: {initial_error}; refresh failure: {refresh_error}",
            registry_failure=RegistryFailureClassification(
                condition=RegistryFailureCondition.TREE_QUIESCENT,
                facts={"path": str(resolved), "registry_tree_quiescent": False, "operation": "registry_tree_refresh"},
            ),
        ) from refresh_error


def _toml_fingerprint(path: Path) -> _RegistryPathFingerprint:
    """Return the ``(path, size, mtime_ns, content_digest)`` fingerprint for one TOML file.

    Delegates to :func:`~dev.registry.compiler.loader_cache.toml_file_fingerprint`,
    the shared primitive that makes mutable-tree fingerprints content-sensitive
    (a same-size, same-mtime rewrite still re-keys every cache above the
    loader) while the read-only bundled tree keeps the cheap stat-only form.
    """
    return toml_file_fingerprint(path)


#: The module boundary used by the public loader for directory compilation.
__all__ = [
    "_RegistryPathFingerprints",
    "_load_catalogue_file_cached",
    "_load_modelo_directory_cached",
    "_refresh_modelo_directory_fingerprints_after_load_error",
    "_refresh_registry_tree_fingerprints_after_load_error",
    "_toml_fingerprint",
    "_validate_legal_directory",
]
