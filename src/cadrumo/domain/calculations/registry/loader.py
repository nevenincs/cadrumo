"""The registry TOML loading contract.

Loading a modelo, a catalogue or the whole registry tree is what callers outside
this package legitimately need; the compilation machinery behind it is private
in :mod:`_loader_internals`.
"""

from __future__ import annotations

from collections.abc import Mapping
from functools import lru_cache
from pathlib import Path

from ....core.directory_scan import (
    scan_directory,
)
from ._compiled_cache import load_compiled_registry_cache, store_compiled_registry_cache
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
    _validate_legal_parameter_refs,
    load_modelo_file,
)
from .errors import (
    RegistryLoadError,
)
from .identity import RegistryIdentity, resolve_registry_identity, stamped_cache_key_tuples
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
from .schema import ModeloDefinition, RegistryCatalogues, SupportedFilingYearsCatalogue
from .schema_references import LegalParameter, LegalReference, SourceReference


def load_modelo_directory(directory: Path) -> ModeloDefinition:
    """Load a :class:`ModeloDefinition` from a directory layout.

    The directory must contain ``manifest.toml`` carrying the ``[modelo]``
    metadata table. Per-revision data lives in ``revisions/{id}.toml``
    files, or in ``revisions/{id}/`` fragment directories. Revision
    files declare one or more revisions via top-level
    ``[revisions."<id>"]`` (and ``[[revisions."<id>".X]]`` array tables).
    Fragment directories declare exactly the directory revision id
    across one or more TOML files using the same table shape. All
    revision sources are merged into the single in-memory
    :class:`ModeloDefinition` that single-file mode produces.

    Public API stays identical to ``load_modelo_file``: callers receive
    the same :class:`ModeloDefinition` regardless of on-disk layout.
    """
    resolved = directory.resolve()
    if not resolved.is_dir():
        raise RegistryLoadError(f"{resolved}: modelo directory does not exist")
    manifest_path = resolved / "manifest.toml"
    if not manifest_path.is_file():
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


def load_modelo_path(path: Path) -> ModeloDefinition:
    """Load a :class:`ModeloDefinition` from either supported on-disk layout."""
    resolved = path.resolve()
    if resolved.is_file():
        return load_modelo_file(resolved)
    if resolved.is_dir():
        return load_modelo_directory(resolved)
    raise RegistryLoadError(f"{resolved}: modelo source does not exist")


def load_modelo_source(source: ModeloSource) -> ModeloDefinition:
    """Load a modelo from a discovered source descriptor.

    Returns:
        The compiled :class:`ModeloDefinition` from the source.
    """
    if source.layout == "single_file":
        return load_modelo_file(source.path)
    return load_modelo_directory(source.path)


def load_catalogue_file(path: Path) -> RegistryCatalogues:
    """Load one shared legal/source catalogue TOML file.

    Returns:
        The compiled :class:`RegistryCatalogues` from the TOML file.
    """
    resolved = path.resolve()
    fingerprint = _toml_fingerprint(resolved)
    try:
        return _load_catalogue_file_cached(str(resolved), fingerprint[1], fingerprint[2], fingerprint[3])
    except RegistryLoadError as exc:
        refreshed = _refresh_toml_fingerprint_after_load_error(resolved, exc)
        if refreshed == fingerprint:
            raise
        return _load_catalogue_file_cached(str(resolved), refreshed[1], refreshed[2], refreshed[3])


def load_legal_parameters_only(root: Path) -> Mapping[str, LegalParameter]:
    """Load only the legal-parameter catalogue from ``root/legal/*.toml``.

    Lightweight cycle-safe entry point. Consumers in ``cadrumo.domain.iva``
    and ``cadrumo.domain.rental`` need parameter values at module-import
    time, but the full :func:`load_registry_tree` path pulls in
    ``_bindings`` which itself imports from ``cadrumo.domain.iva`` — a
    circular import.

    This function reuses :func:`load_catalogue_file` (already
    Pydantic-validated and ``lru_cache``-deduplicated) and walks only
    ``root/legal/*.toml``. Modelo parsing and binding validation do not
    run; the legal refs carried by returned parameters are still resolved
    against the legal catalogue.

    Args:
        root: Repository ``registry/aeat`` directory.

    Returns:
        Frozen mapping of parameter-id → :class:`LegalParameter`.

    Raises:
        RegistryLoadError: When duplicate legal or parameter ids are found
            across multiple TOML files in ``root/legal/``.
    """
    return load_shared_catalogues(root).parameters


def load_shared_catalogues(root: Path) -> RegistryCatalogues:
    """Load registry legal, source, and parameter catalogues without modelos.

    This is the canonical cycle-safe catalogue boundary.  IVA grounding needs
    registry evidence while registry modelo compilation imports IVA domain
    types, so constructing the full registry tree here would recurse through
    bindings unnecessarily.
    """
    resolved = root.resolve()
    legal_dir = resolved / "legal"
    _validate_legal_directory(legal_dir)
    legal: dict[str, LegalReference] = {}
    sources: dict[str, SourceReference] = {}
    parameters: dict[str, LegalParameter] = {}
    supported_filing_years: SupportedFilingYearsCatalogue | None = None
    for path in scan_directory(legal_dir, pattern="*.toml"):
        catalogue = load_catalogue_file(path)
        overlap_legal = set(legal).intersection(catalogue.legal)
        overlap_sources = set(sources).intersection(catalogue.sources)
        overlap_parameters = set(parameters).intersection(catalogue.parameters)
        if overlap_legal or overlap_sources or overlap_parameters:
            raise RegistryLoadError(
                f"{path}: duplicate catalogue ids legal={sorted(overlap_legal)!r} "
                f"sources={sorted(overlap_sources)!r} parameters={sorted(overlap_parameters)!r}",
            )
        if catalogue.supported_filing_years is not None:
            if supported_filing_years is not None:
                raise RegistryLoadError(
                    f"{path}: supported_filing_years is already declared by another shared catalogue file",
                )
            supported_filing_years = catalogue.supported_filing_years
        legal.update(catalogue.legal)
        sources.update(catalogue.sources)
        parameters.update(catalogue.parameters)
    _validate_legal_parameter_refs(legal_dir, parameters=parameters, legal=legal)
    if supported_filing_years is None:
        raise RegistryLoadError(f"{legal_dir}: missing supported_filing_years catalogue declaration")
    return RegistryCatalogues(
        legal=legal,
        sources=sources,
        parameters=parameters,
        supported_filing_years=supported_filing_years,
    )


def load_registry_tree(
    root: Path,
    *,
    identity: RegistryIdentity | None = None,
) -> tuple[tuple[ModeloDefinition, ...], RegistryCatalogues]:
    """Load all registry files from ``root``.

    Discovers modelos in two layouts:
      * single-file: ``modelos/<id>.toml``
      * directory:   ``modelos/<id>/manifest.toml`` + ``modelos/<id>/revisions/*.toml``

    A single modelo cannot exist in both layouts simultaneously; the
    loader raises ``RegistryLoadError`` if both forms are present.

    ``identity`` is the caller's already-resolved tree identity, passed by the
    authority so one stamp read serves both. It is a HINT about the tree, never
    a key the caller chooses: on a walked tree this function collects its own
    tree-scoped fingerprints regardless, because the compiled-artefact key must
    be identical for every caller of this function or the cross-process share
    the artefact exists to deliver fragments per call site. Omitted, the
    identity is resolved here through the same canonical resolver.

    On a STAMPED tree the structural discovery pass is skipped along with the
    fingerprint walk. That pass exists so a malformed tree is refused even when
    the compiled artefact hits; on a stamped install the build already proved
    the structure, and on an artefact MISS the compile re-discovers and refuses
    anyway, so the refusal is preserved wherever it can still fire.

    Returns:
        A tuple of all :class:`ModeloDefinition` objects and the merged :class:`RegistryCatalogues`.
    """
    resolved = root.resolve()
    if identity is None:
        identity = resolve_registry_identity(
            resolved,
            collect_fingerprints=_collect_registry_tree_fingerprints,
        )
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
    root: str,
    fingerprints: _RegistryPathFingerprints,
) -> tuple[tuple[ModeloDefinition, ...], RegistryCatalogues]:
    resolved = Path(root)
    use_disk_cache = registry_disk_cache_enabled(is_bundled=is_bundled_registry_root(resolved))
    if use_disk_cache:
        # A strict-validated compiled cache lets a warm
        # process skip the TOML parse. It is a shortcut to the same compiled
        # authority, never a second one: the loader here is the sole compile
        # path, and the cache read integrity-checks and structurally validates
        # the payload, deleting and recompiling on any mismatch.
        cached = load_compiled_registry_cache(resolved, fingerprints)
        if cached is not None:
            return cached

    catalogues = load_shared_catalogues(resolved)
    modelos = _load_all_modelo_definitions(resolved / "modelos")
    result = (modelos, catalogues)

    if use_disk_cache:
        store_compiled_registry_cache(resolved, fingerprints, result)
    return result


def _load_all_modelo_definitions(modelos_dir: Path) -> tuple[ModeloDefinition, ...]:
    """Load every modelo (single-file + directory-mode) and reject layout collisions.

    A modelo id present both as ``modelos/<id>.toml`` and as
    ``modelos/<id>/manifest.toml`` is a configuration mistake — the
    loader cannot tell which layout is authoritative, so it raises
    instead of silently picking one.
    """
    return tuple(load_modelo_source(source) for source in discover_modelo_sources(modelos_dir))


collect_registry_tree_fingerprints = _collect_registry_tree_fingerprints


def clear_registry_tree_cache() -> None:
    """Drop the memoised registry-tree loads.

    A test that writes a registry tree to a temp directory and loads it needs
    the memo cleared between cases. Exposing the reset here keeps the cache
    itself private: the reset is the contract, the cache is not.
    """
    _load_registry_tree_cached.cache_clear()
