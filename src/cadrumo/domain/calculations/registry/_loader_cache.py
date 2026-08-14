"""Registry loader cache predicates.

This module centralizes the small policy decisions that keep registry loading
fast without hiding live TOML edits. Bundled registry roots receive a short
fingerprint TTL, mutable authoring roots keep the stricter window, and under
pytest the cross-process disk pickle is shared only for the immutable
bundled root -- a mutable/synthetic root always keeps it disabled so xdist
workers cannot share a stale compiled registry from a tree the run itself
can edit.

See Also:
    :mod:`~domain.calculations.registry._loader`
        Registry TOML loader that consumes these TTL and disk-cache predicates.
    :func:`~core.resources.bundled_path`
        Resource boundary used to identify the package-bundled registry root.
    :func:`~domain.calculations.registry.tests.test_loader_cache_isolation.test_registry_disk_cache_disabled_under_pytest_for_a_mutable_root`
        Real-behavior gate for the pytest disk-cache refusal path.
    :func:`~domain.calculations.registry.tests.test_loader_cache_isolation.test_is_bundled_registry_root_rejects_a_mutable_authoring_tree`
        Coverage for bundled-root versus mutable-authoring-tree separation.
    :func:`~domain.calculations.registry.tests.test_loader_cache_isolation.test_bundled_tree_fingerprint_cache_survives_past_the_mutable_tree_ttl`
        Coverage for the longer bundled-root fingerprint TTL window.
    :func:`~conftest._isolate_registry_caches`
        Session fixture that clears registry caches around pytest runs.
"""

from __future__ import annotations

import hashlib
import re
import tempfile
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Literal

from ....core import StorageCategory, freeze_toml, read_toml, storage_location
from ....core.config import load_settings
from ....core.resources import bundled_path
from ._errors import RegistryLoadError
from ._ids import RevisionId
from ._toml_helpers import as_toml_table as _as_toml_table

REGISTRY_DISK_CACHE_DIR_ENV_VAR = "CADRUMO_REGISTRY_DISK_CACHE_DIR"
"""Environment variable backing :attr:`~core.config.Settings.cadrumo_registry_disk_cache_dir`."""

# The production branch's relative path, read off the taxonomy rather than an
# untethered ``"cache" / "registry"`` literal -- the member's name is governed
# there (see its declaration in ``core._storage_taxonomy``), while the field
# itself stays deliberately un-derived so the pytest branch below can keep
# selecting on it being unset.
_REGISTRY_DISK_CACHE_RELATIVE_PATH = storage_location(StorageCategory.REGISTRY_DISK_CACHE).relative_path()

# The bundled tree gets a longer fingerprint TTL than a mutable authoring
# tree, but NOT a process-lifetime one: under an editable install (the
# routine development mode) "bundled" resolves to the literal in-tree
# ``src/cadrumo/_data/registry/aeat`` source directory, which can be edited
# live during a session. A TTL that
# never re-checks would silently serve stale registry TOML to a long-running
# process (an MCP server, a REPL, a background watch loop) after such an
# edit lands. 10 seconds is long enough to fold the several fingerprint
# recomputations one calculate call triggers (authority + snapshot + any
# nested revision lookups, all milliseconds apart) into a single directory
# walk, while still re-scanning promptly enough that a concurrent registry
# edit is picked up well within one operator interaction. A genuinely
# read-only installed (non-editable) wheel benefits identically: nothing
# ever rewrites it, so the periodic re-walk merely repeats the same answer.
BUNDLED_REGISTRY_FINGERPRINT_TTL_SECONDS = 10.0
MUTABLE_REGISTRY_FINGERPRINT_TTL_SECONDS = 1.0

ModeloSourceLayout = Literal["single_file", "directory"]
ModeloRevisionSourceLayout = Literal["revision_file", "fragment_directory"]

_ADMINISTRATIVE_FRAGMENT_NAME = re.compile(
    r"^(?P<prefix>[0-9]{4})-[a-z0-9](?:[a-z0-9]|[.-](?=[a-z0-9]))*\.toml$",
)
_CASILLA_FRAGMENT_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9+_.-]*\.toml$")
_CONTINUIDAD_FRAGMENT_NAME = re.compile(r"^[a-z0-9][a-z0-9.-]*\.toml$")
_SOURCE_NATIVE_FRAGMENT_SECTIONS = frozenset({"casillas", "casilla_continuidad_evolutions"})
_GENERATED_EXPORT_PROVENANCE_FILENAME = "_generation.provenance.json"


@dataclass(frozen=True, slots=True)
class ModeloRevisionSource:
    """On-disk source for one modelo revision before schema validation."""

    revision_id: RevisionId
    layout: ModeloRevisionSourceLayout
    path: Path
    fragment_paths: tuple[Path, ...]


@dataclass(frozen=True, slots=True)
class ModeloSource:
    """On-disk source for one modelo before schema validation."""

    modelo_id: str
    layout: ModeloSourceLayout
    path: Path
    manifest_path: Path
    revision_sources: tuple[ModeloRevisionSource, ...] = ()


def discover_modelo_sources(modelos_dir: Path) -> tuple[ModeloSource, ...]:
    """Discover single-file and directory-mode modelo sources."""
    resolved = modelos_dir.resolve()
    _validate_modelos_directory_entries(resolved)
    sources: list[ModeloSource] = []
    seen_modelo_ids: dict[str, ModeloSource] = {}
    for source in _single_file_modelo_sources(resolved):
        _append_modelo_source(source, sources, seen_modelo_ids)
    for source in _directory_modelo_sources(resolved):
        _append_modelo_source(source, sources, seen_modelo_ids)
    return tuple(sources)


def _validate_modelos_directory_entries(modelos_dir: Path) -> None:
    """Refuse plausible modelo sources that discovery would otherwise ignore."""
    if not modelos_dir.is_dir():
        return
    for entry in sorted(modelos_dir.iterdir()):
        if entry.is_file():
            if entry.suffix != ".toml":
                raise RegistryLoadError(
                    f"{entry}: unrecognized modelos file; modelo files must use the '.toml' suffix",
                )
            continue
        if entry.is_dir():
            if not (entry / "manifest.toml").is_file():
                raise RegistryLoadError(
                    f"{entry}: orphan modelo directory; directory-mode modelos must contain manifest.toml",
                )
            continue
        raise RegistryLoadError(f"{entry}: unrecognized modelos entry")


def _read_modelo_id(path: Path, *, description: str) -> str:
    try:
        raw_data = read_toml(path, error_factory=RegistryLoadError)
        modelo_table = _as_toml_table(raw_data.get("modelo"))
        if modelo_table is None or "id" not in modelo_table:
            raise RegistryLoadError(f"{path}: missing [modelo].id")
        return str(modelo_table["id"])
    except Exception as exc:
        raise RegistryLoadError(f"{path}: invalid {description}: {exc}") from exc


def _single_file_modelo_sources(modelos_dir: Path) -> tuple[ModeloSource, ...]:
    return tuple(
        ModeloSource(
            modelo_id=_read_modelo_id(path, description="modelo file"),
            layout="single_file",
            path=path.resolve(),
            manifest_path=path.resolve(),
        )
        for path in sorted(modelos_dir.glob("*.toml"))
    )


def _directory_modelo_sources(modelos_dir: Path) -> tuple[ModeloSource, ...]:
    if not modelos_dir.is_dir():
        return ()
    return tuple(
        _directory_modelo_source(entry)
        for entry in sorted(modelos_dir.iterdir())
        if entry.is_dir() and (entry / "manifest.toml").is_file()
    )


def _directory_modelo_source(entry: Path) -> ModeloSource:
    validate_modelo_directory_source(entry)
    manifest_path = entry / "manifest.toml"
    return ModeloSource(
        modelo_id=_read_modelo_id(manifest_path, description="manifest"),
        layout="directory",
        path=entry.resolve(),
        manifest_path=manifest_path.resolve(),
        revision_sources=_discover_revision_sources(entry / "revisions"),
    )


def validate_modelo_directory_source(entry: Path) -> None:
    """Validate every entry that belongs to one directory-mode modelo source."""
    allowed_directories = frozenset({"locales", "revisions"})
    for child in sorted(entry.iterdir()):
        if child.is_file():
            if child.name != "manifest.toml":
                raise RegistryLoadError(f"{child}: unrecognized modelo source file; only manifest.toml is allowed")
            continue
        if child.is_dir():
            if child.name not in allowed_directories:
                raise RegistryLoadError(f"{child}: unrecognized modelo source directory")
            if child.name == "locales":
                _validate_flat_toml_files(child, description="modelo locale")
            continue
        raise RegistryLoadError(f"{child}: unrecognized modelo source entry")
    _discover_revision_sources(entry / "revisions")


def _validate_flat_toml_files(directory: Path, *, description: str) -> None:
    for entry in sorted(directory.iterdir()):
        if not entry.is_file() or entry.suffix != ".toml":
            raise RegistryLoadError(f"{entry}: unrecognized {description} entry; only TOML files are allowed")


def _append_modelo_source(
    source: ModeloSource,
    sources: list[ModeloSource],
    seen_modelo_ids: dict[str, ModeloSource],
) -> None:
    previous = seen_modelo_ids.get(source.modelo_id)
    if previous is not None:
        raise RegistryLoadError(
            f"{source.path}: modelo {source.modelo_id!r} also declared at {previous.path}; "
            "remove one of the two layouts",
        )
    seen_modelo_ids[source.modelo_id] = source
    sources.append(source)


def _discover_revision_sources(revisions_dir: Path) -> tuple[ModeloRevisionSource, ...]:
    if not revisions_dir.is_dir():
        return ()
    _validate_revision_directory_entries(revisions_dir)
    file_sources = tuple(
        source for path in sorted(revisions_dir.glob("*.toml")) for source in _revision_file_sources(path)
    )
    directory_sources = tuple(
        _revision_directory_source(path) for path in sorted(revisions_dir.iterdir()) if path.is_dir()
    )
    return (*file_sources, *directory_sources)


def _validate_revision_directory_entries(revisions_dir: Path) -> None:
    for entry in sorted(revisions_dir.iterdir()):
        if entry.is_file() and entry.suffix != ".toml":
            raise RegistryLoadError(
                f"{entry}: unrecognized revision file; revision files must use the '.toml' suffix",
            )
        if not entry.is_file() and not entry.is_dir():
            raise RegistryLoadError(f"{entry}: unrecognized revisions entry")


def _revision_file_sources(path: Path) -> tuple[ModeloRevisionSource, ...]:
    rev_data = freeze_toml(read_toml(path, error_factory=RegistryLoadError))
    file_revisions = _as_toml_table(rev_data.get("revisions"))
    if not file_revisions:
        raise RegistryLoadError(f"{path}: revision file must declare [revisions.<id>]")
    return tuple(
        ModeloRevisionSource(
            revision_id=revision_id,
            layout="revision_file",
            path=path,
            fragment_paths=(path,),
        )
        for revision_id in sorted(file_revisions)
    )


def _revision_directory_source(path: Path) -> ModeloRevisionSource:
    _validate_revision_fragment_tree(path)
    revision_manifest = path / "revision.toml"
    fragment_paths = (revision_manifest,) if revision_manifest.is_file() else ()
    fragment_paths = (
        *fragment_paths,
        *tuple(
            p
            for p in sorted(path.glob("*/*.toml"))
            if p != revision_manifest and not any(part == "locales" for part in p.parts)
        ),
    )
    return ModeloRevisionSource(
        revision_id=path.name,
        layout="fragment_directory",
        path=path,
        fragment_paths=fragment_paths,
    )


def _validate_revision_fragment_tree(path: Path) -> None:
    """Reject ignored files and enforce schema-family-aware fragment names."""
    _validate_revision_fragment_top_level(path)
    _validate_revision_fragment_file_suffixes(path)
    for section_dir in _revision_fragment_section_directories(path):
        _validate_section_fragment_names(section_dir)


def _validate_revision_fragment_top_level(path: Path) -> None:
    for entry in sorted(path.iterdir()):
        if entry.is_file() and entry.name != "revision.toml":
            raise RegistryLoadError(
                f"{entry}: revision section fragment must live in its owned section subdirectory",
            )


def _validate_revision_fragment_file_suffixes(path: Path) -> None:
    for entry in sorted(path.rglob("*")):
        if entry.is_file() and entry.suffix != ".toml" and not _is_generated_export_provenance(entry, path):
            raise RegistryLoadError(
                f"{entry}: unrecognized revision fragment file; fragments must use the '.toml' suffix",
            )


def _is_generated_export_provenance(entry: Path, revision_root: Path) -> bool:
    """Recognise the one generator-owned non-TOML revision artefact."""
    return entry.name == _GENERATED_EXPORT_PROVENANCE_FILENAME and entry.parent == revision_root / "export"


def _revision_fragment_section_directories(path: Path) -> tuple[Path, ...]:
    return tuple(sorted(entry for entry in path.iterdir() if entry.is_dir() and entry.name != "locales"))


def _validate_section_fragment_names(section_dir: Path) -> None:
    nested_entries = sorted(entry for entry in section_dir.iterdir() if entry.is_dir())
    if nested_entries:
        raise RegistryLoadError(
            f"{nested_entries[0]}: nested revision section directories are not allowed; "
            "fragments must be direct children of their owned section directory",
        )
    fragment_paths = sorted(section_dir.glob("*.toml"))
    if section_dir.name == "casillas":
        pattern = _CASILLA_FRAGMENT_NAME
        description = "casilla source-native"
    elif section_dir.name == "casilla_continuidad_evolutions":
        pattern = _CONTINUIDAD_FRAGMENT_NAME
        description = "casilla continuity source-native"
    else:
        pattern = _ADMINISTRATIVE_FRAGMENT_NAME
        description = "numbered administrative"

    prefixes: dict[str, Path] = {}
    for fragment_path in fragment_paths:
        match = pattern.fullmatch(fragment_path.name)
        if match is None:
            raise RegistryLoadError(
                f"{fragment_path}: invalid {description} fragment filename",
            )
        if section_dir.name in _SOURCE_NATIVE_FRAGMENT_SECTIONS:
            continue
        prefix = match.group("prefix")
        previous = prefixes.get(prefix)
        if previous is not None:
            raise RegistryLoadError(
                f"{fragment_path}: duplicate administrative fragment prefix {prefix!r} in {section_dir}; "
                f"already used by {previous.name}",
            )
        prefixes[prefix] = fragment_path


@lru_cache(maxsize=1)
def _bundled_registry_root() -> Path:
    """Return the resolved package-bundled registry root, computed once per process."""
    return bundled_path("registry", "aeat").resolve()


def is_bundled_registry_root(resolved: Path) -> bool:
    """Whether ``resolved`` is the package-bundled registry tree.

    The bundled tree is shipped inside the installed wheel (or, under an
    editable install, force-included from the in-tree ``registry/aeat``
    directory) rather than passed explicitly as a mutable authoring tree
    (e.g. a test's ``tmp_path`` fixture building a synthetic registry).
    Comparing the resolved path against the bundled root lets the
    fingerprint cache apply :data:`BUNDLED_REGISTRY_FINGERPRINT_TTL_SECONDS`
    to the bundled tree alone without weakening invalidation for any
    mutable tree, which always keeps the strict
    :data:`MUTABLE_REGISTRY_FINGERPRINT_TTL_SECONDS` window.
    """
    try:
        return resolved == _bundled_registry_root()
    except (ImportError, OSError, ValueError):
        # A resources boundary failure (e.g. no bundled data under an unusual
        # install) must never be mistaken for "this is the bundled tree";
        # fail closed to the strict mutable-tree TTL.
        return False


def is_bundled_registry_path(path: Path) -> bool:
    """Whether ``path`` lies inside the package-bundled registry tree.

    Path-containment sibling of :func:`is_bundled_registry_root`, used by the
    per-file fingerprint to decide whether a content digest must be computed:
    the bundled tree is read-only package data that is never rewritten during
    a process's lifetime (the same immutability premise the pytest disk-cache
    predicate and the longer bundled TTL already rely on), so its files keep
    the cheap stat-only fingerprint, while any mutable authoring tree -- the
    only place an in-run rewrite can collide on ``(size, mtime_ns)`` -- pays
    for the content discriminator. ``path`` must already be resolved. Fails
    closed to ``False`` (content-sensitive fingerprinting) on any resources
    boundary failure.
    """
    try:
        return path.is_relative_to(_bundled_registry_root())
    except (ImportError, OSError, ValueError):
        return False


def toml_file_fingerprint(path: Path) -> tuple[str, int, int, str]:
    """Return the ``(path, size, mtime_ns, content_digest)`` fingerprint for one registry TOML.

    The shared per-file fingerprint primitive behind the loader's cache keys
    and the convenio treaty fingerprints. ``(size, mtime_ns)`` alone cannot
    distinguish two successive writes that produce content of the same byte
    length within the filesystem's effective mtime resolution (coarse on CI
    overlay/network filesystems), so a stat-only fingerprint would serve a
    stale compiled registry after such an edit -- violating the
    complete-tree-fingerprint invariant of the registry authority flow. The
    content digest closes that hole; the stat fields remain as the cheap
    first-order discriminator.

    The package-bundled tree is exempt (empty digest): it is read-only package
    data never rewritten during a process's lifetime -- the same immutability
    premise the pytest disk-cache predicate and the longer bundled TTL already
    encode (:func:`is_bundled_registry_path`) -- and hashing its ~16.5k TOML
    files (~25 MB) would add ~1.3 s to every cold fingerprint walk for a tree
    that cannot exhibit the collision.
    """
    try:
        stat = path.stat()
    except OSError as exc:
        raise RegistryLoadError(
            f"{path}: registry TOML could not be fingerprinted; retry after concurrent registry writes settle: {exc}",
        ) from exc
    return str(path), stat.st_size, stat.st_mtime_ns, _toml_content_digest(path)


def _toml_content_digest(path: Path) -> str:
    """Return the mutable-tree content discriminator, or ``""`` for bundled files."""
    if is_bundled_registry_path(path):
        return ""
    try:
        data = path.read_bytes()
    except OSError as exc:
        raise RegistryLoadError(
            f"{path}: registry TOML could not be fingerprinted; retry after concurrent registry writes settle: {exc}",
        ) from exc
    return hashlib.blake2b(data, digest_size=16).hexdigest()


def _running_under_pytest() -> bool:
    """Whether the current process is a pytest run (including collection and xdist workers)."""
    import os
    import sys

    return (
        "pytest" in sys.modules
        or "PYTEST_CURRENT_TEST" in os.environ
        or "PYTEST_XDIST_WORKER" in os.environ
        or "PYTEST_VERSION" in os.environ
    )


def registry_disk_cache_enabled(*, is_bundled: bool = False) -> bool:
    """Whether the cross-process ``/tmp`` registry pickle is read/written.

    Production (no pytest markers present at all) always keeps the disk
    cache: it loads the registry once at startup with no concurrent edits.

    Under pytest, including collection before ``PYTEST_CURRENT_TEST`` is
    set, the cache is enabled ONLY for ``is_bundled=True`` -- the
    package-bundled, read-only registry tree (:func:`is_bundled_registry_root`).
    That tree is never mutated during a test run, so every pytest-xdist
    worker and every subprocess-spawning test may safely share ONE compiled
    pickle keyed by a content fingerprint of that tree, collapsing what would
    otherwise be an independent multi-second cold compile per worker/subprocess
    into a single shared compile the rest read.

    A mutable or synthetic root (e.g. a test's ``tmp_path`` registry, or any
    path that is not the resolved bundled root) always keeps the cache
    disabled under pytest -- this is the #44 isolation fix: such a root CAN be
    edited mid-run by the very test that built it, and the pickle is keyed by
    file mtime, so sharing it across workers could serve a stale or
    transiently-inconsistent compiled registry (the M303-2009 flake #44
    diagnosed). Only the always-immutable bundled tree is exempt from that
    race.
    """
    if _running_under_pytest():
        return is_bundled
    return True


def registry_disk_cache_dir() -> Path:
    """Return the directory the cross-process registry disk pickle lives in.

    Resolution precedence:

    1. An explicit :attr:`~core.config.Settings.cadrumo_registry_disk_cache_dir`
       (the ``CADRUMO_REGISTRY_DISK_CACHE_DIR`` env var) always wins. A test
       that needs to assert EXCLUSIVE state on the pickle (e.g. "exactly one
       file exists", "the mtime is unchanged") sets this to a test-owned
       directory, so its assertions are not confused by sibling pytest-xdist
       workers touching the shared bundled-root pickle -- while still
       exercising the real filesystem and read/write path. It rides the env
       var (not a monkeypatch) so it also propagates to a subprocess a test
       spawns via ``env=``.
    2. Production (not under pytest) derives
       ``<cadrumo_local_storage_root>/cache/registry`` -- one per-user location
       under the single storage root, never the shared OS temp directory that
       any two host users could collide in.
    3. Under pytest with no explicit override, the cross-worker bundled-root
       share stays in the host-shared OS temp directory: xdist workers each
       get a per-pid ``cadrumo_local_storage_root``, so deriving from it would
       give every worker a private cache and defeat the single-compile sharing
       the disk pickle exists to deliver. The bundled tree is immutable during
       a run, so one host-shared compiled pickle is safe to share. This
       divergence from the member's declared subpath is a positive, test-pinned
       exception rather than an undeclared special case -- see
       :attr:`~core.StorageLocation.test_pinned_exception` on
       ``StorageCategory.REGISTRY_DISK_CACHE``.
    """
    settings = load_settings()
    return _resolve_registry_disk_cache_dir(
        override=settings.cadrumo_registry_disk_cache_dir,
        under_pytest=_running_under_pytest(),
        storage_root=settings.cadrumo_local_storage_root,
    )


def _resolve_registry_disk_cache_dir(*, override: Path | None, under_pytest: bool, storage_root: Path) -> Path:
    """Pure resolution of the registry disk-cache directory.

    Split from :func:`registry_disk_cache_dir` so the three branches (explicit
    override, pytest host-shared temp, production storage-root derivation) are
    exercised with real inputs rather than by manipulating the ambient process.
    """
    if override is not None:
        return override
    if under_pytest:
        return Path(tempfile.gettempdir())
    return storage_root / _REGISTRY_DISK_CACHE_RELATIVE_PATH


def registry_disk_cache_max_entries() -> int:
    """Return the retained-pickle ceiling for registry disk-cache eviction.

    Reads :attr:`~core.config.Settings.cadrumo_registry_disk_cache_max_entries`;
    the loader prunes the oldest pickles beyond this count after each write.
    """
    return load_settings().cadrumo_registry_disk_cache_max_entries
