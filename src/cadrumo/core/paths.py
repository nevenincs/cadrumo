"""Shared path normalization and containment helpers.

Centralises the small set of :class:`~pathlib.Path` primitives that every other
Cadrumo module needs: resolving relative operator paths against the
application-data anchor via :func:`resolve_project_path`, normalising settings
with :func:`normalize_project_relative_path`, and safely resolving
caller-provided sub-paths under a fixed root without allowing path-traversal
escapes.

The containment helper :func:`resolve_relative_subpath` refuses backslashes,
parent references, absolute components, and any resolved path that escapes the
owning root. It raises :class:`~cadrumo.core.errors.CoreValidationError` and is
the load-bearing defence against caller-controlled identifier injection on the
on-disk store paths.

These helpers validate and compose paths only. They do not read, write,
create, or secure files; persistence adapters that need registered storage
errors wrap this module in their own typed containment layer.

:func:`is_windows_long_path_error`, :func:`windows_long_paths_enabled`, and
:func:`windows_storage_root_long_path_margin` are the Windows ``MAX_PATH``
(260-character) hardening surface: classifying an ``OSError`` that legacy
Windows raises once a resolved path exceeds the limit, reading the
machine-wide long-path opt-in, and computing whether a candidate storage root
leaves enough headroom for the deepest object path the bucket / outbound
storage layout can produce.
"""

from __future__ import annotations

import sys
from collections.abc import Callable, Iterable, Sequence
from functools import lru_cache
from pathlib import Path, PurePosixPath
from stat import S_ISREG
from typing import TYPE_CHECKING, Any, Literal, Protocol

from ._config_state_root import (
    StateRootInputs,
    live_state_root_inputs,
    platform_user_data_root,
)
from .errors import CoreValidationError

if TYPE_CHECKING:
    from .config import Settings


def _relative_path_anchor(state_root_inputs: StateRootInputs | None = None) -> Path:
    """Return the base a relative operator path resolves against.

    Always the platform user-data directory
    (:func:`cadrumo.core._config_state_root.platform_user_data_root`), the
    same root :func:`~cadrumo.core._config_state_root.resolve_state_root`
    hands the storage default. A relative override of a ``var/``-style
    operator setting (storage root, cache dir, log dir, financial catalogue
    dir, ...) therefore lands beside the state it belongs with, and can
    never resolve inside a virtualenv or an ephemeral package cache.

    There is no source-checkout arm. An earlier revision branched here on
    whether the process was running from a repository, which made a
    source-layout guess decide where operator data was written; a
    tax-filing product does not classify its own installation. A developer
    who wants a checkout-local location sets the corresponding setting
    explicitly, and an explicit override wins over this anchor.

    Args:
        state_root_inputs: Injectable
            :class:`~cadrumo.core._config_state_root.StateRootInputs` seam.
            ``None`` (the live default) captures the running process's
            inputs via
            :func:`~cadrumo.core._config_state_root.live_state_root_inputs`
            — the same seam
            :func:`~cadrumo.core._config_state_root.default_storage_root`
            reads, so a relative override and the unset default resolve
            consistently.
    """
    inputs = state_root_inputs if state_root_inputs is not None else live_state_root_inputs()
    return platform_user_data_root(inputs)


# ── Windows MAX_PATH (260-character) hardening ────────────────────────────

#: Legacy Windows ``CreateFileW`` path-length ceiling in UTF-16 code units.
#: Windows 10 1607+ can lift this per-application via the
#: ``LongPathsEnabled`` registry value combined with a
#: ``longPathAware`` application manifest; a workstation that has neither
#: still enforces this ceiling.
WINDOWS_MAX_PATH: int = 260

#: ``WinError 3`` — ``ERROR_PATH_NOT_FOUND`` ("The system cannot find the
#: path specified."). Windows raises this — instead of a length-specific
#: error — when a directory creation walks past ``MAX_PATH`` on a legacy
#: (non long-path-aware) configuration.
_WIN_ERROR_PATH_NOT_FOUND = 3

#: ``WinError 206`` — ``ERROR_FILENAME_EXCED_RANGE`` ("The filename or
#: extension is too long."). Windows raises this when the final path
#: component itself pushes the full path past the length ceiling.
_WIN_ERROR_FILENAME_EXCED_RANGE = 206

_WINDOWS_LONG_PATH_WINERRORS = frozenset({_WIN_ERROR_PATH_NOT_FOUND, _WIN_ERROR_FILENAME_EXCED_RANGE})

#: Worst-case path suffix (leading separator through file extension) that
#: the bucket-directory layout can append below a configured storage root.
#: Mirrors the ``local_provider_object_sidecar`` grammar declared in
#: :data:`cadrumo.adapters.persistence.storage.STORAGE_NAMESPACE_REGISTRY`
#: (``<root>/buckets/<bucket_id>/blobs/<namespace>/<hmac_prefix>--<label>.meta.json``),
#: not the earlier, shorter mirror
#: (``\buckets\<uuid-36>\blobs\<hmac-8>--<label-64>.meta.json``) that omitted
#: the ``<namespace>`` segment ``LocalFileSystemProvider`` fans out one
#: directory per outbound-attachment namespace into
#: (``_local.py:176``/``:292``, ``self._root / namespace``) -- the omission
#: understated the true worst case by 19 characters (136 measured versus the
#: correct 155), which could let the preflight margin in
#: :func:`windows_storage_root_long_path_margin` accept a storage root from
#: which a real outbound write then exceeds ``MAX_PATH``.
#:
#: ``bucket_id`` is a 36-character UUID; ``hmac_prefix`` is 8 hex characters;
#: ``label`` is capped at 64 characters
#: (:func:`~adapters.outbound.storage.sanitize_provider_object_label`).
#: ``namespace`` carries no enforced length cap today -- ``ledger_transaction``
#: (:class:`~domain.buckets.BucketEventObjectType`, the object-type catalogue
#: an outbound attachment namespaces by) is used here as a real, representative
#: value, not a structurally-guaranteed ceiling; a longer namespace value
#: would understate the margin again. Tracked as a separate finding, not
#: fixed here.
#: Kept as a literal here (not imported) because this module sits below the
#: persistence and outbound-storage layers in the dependency graph; the
#: two call sites that use this constant assert their real deepest-suffix
#: shapes against it in tests.
WINDOWS_WORST_CASE_OBJECT_PATH_SUFFIX_LENGTH: int = len(
    "\\buckets\\"
    + ("0" * 36)
    + "\\blobs\\"
    + "ledger_transaction"
    + "\\"
    + ("a" * 8)
    + "--"
    + ("b" * 64)
    + ".meta.json",
)


def is_windows_long_path_error(exc: OSError) -> bool:
    """Return whether ``exc`` is a Windows path-length-ceiling failure.

    Classifies ``WinError 3`` (``ERROR_PATH_NOT_FOUND``) and ``WinError
    206`` (``ERROR_FILENAME_EXCED_RANGE``) — the two concrete Windows API
    error codes a legacy (non long-path-aware) workstation raises once a
    resolved path walks past :data:`WINDOWS_MAX_PATH`. Always ``False`` on
    non-Windows platforms and for any other ``OSError``, so callers can
    unconditionally probe every caught ``OSError`` without a platform
    guard of their own.

    Args:
        exc: The caught :class:`OSError` (or subclass, e.g.
            :class:`FileNotFoundError`) to classify.

    Returns:
        ``True`` when ``exc.winerror`` names a known long-path failure.
    """
    if sys.platform != "win32":
        return False
    return getattr(exc, "winerror", None) in _WINDOWS_LONG_PATH_WINERRORS


def windows_long_paths_enabled() -> bool | None:
    r"""Report the machine-wide Windows long-path opt-in, if determinable.

    Reads ``HKEY_LOCAL_MACHINE\SYSTEM\CurrentControlSet\Control\FileSystem
    \LongPathsEnabled`` — the registry value Windows 10 1607+ consults to
    lift :data:`WINDOWS_MAX_PATH` for manifest-declared long-path-aware
    applications (this CLI is built with a ``longPathAware`` manifest via
    its packaging).

    Returns:
        ``True`` when the value is present and non-zero, ``False`` when
        present and zero (or when the platform is Windows but the value is
        absent — the pre-1607 / not-yet-opted-in default), and ``None`` on
        a non-Windows platform where the concept does not apply, or when
        the registry cannot be read at all (a probe is best-effort; it
        never raises).
    """
    if sys.platform != "win32":
        return None
    try:
        import winreg
    except ImportError:  # pragma: no cover - winreg is stdlib on win32
        return None
    try:
        with winreg.OpenKey(
            winreg.HKEY_LOCAL_MACHINE,
            r"SYSTEM\CurrentControlSet\Control\FileSystem",
        ) as key:
            value, _kind = winreg.QueryValueEx(key, "LongPathsEnabled")
    except OSError:
        # Key or value absent, or unreadable under the current privilege
        # level: report the conservative pre-opt-in default rather than
        # raising out of a best-effort probe.
        return False
    return bool(value)


def windows_storage_root_long_path_margin(root: Path) -> int:
    """Return the headroom, in characters, before an object write risks ``MAX_PATH``.

    Computes ``WINDOWS_MAX_PATH - len(str(root.resolve())) -
    WINDOWS_WORST_CASE_OBJECT_PATH_SUFFIX_LENGTH``. A positive result is
    the number of characters of slack remaining; zero or negative means
    the deepest object the bucket / outbound-storage layout can write
    already meets or exceeds the legacy ``MAX_PATH`` ceiling from this
    root. Platform-independent by design: the margin is informative on
    every OS, but only Windows without the long-path opt-in enforces the
    ceiling it measures against.

    Args:
        root: The candidate storage root (``cadrumo_local_storage_root`` or
            an outbound-storage provider root).

    Returns:
        The signed character margin described above.
    """
    resolved_length = len(str(root.resolve()))
    return WINDOWS_MAX_PATH - resolved_length - WINDOWS_WORST_CASE_OBJECT_PATH_SUFFIX_LENGTH


def resolve_project_path(value: str | Path, *, state_root_inputs: StateRootInputs | None = None) -> Path:
    """Resolve a relative path against the application-data anchor.

    Absolute paths are returned as absolute resolved paths. Relative paths
    are interpreted against :func:`_relative_path_anchor` — never the
    process cwd, which keeps config defaults stable regardless of where the
    CLI process starts, and never a bare checkout-root walk, which keeps an
    installed run's relative override out of a virtualenv or ephemeral
    package cache. This helper is not a containment guard: callers that
    accept subpaths under an owning root should use
    :func:`resolve_relative_subpath`.

    Args:
        value: An absolute or relative path; user-style ``~`` references
            are expanded.
        state_root_inputs: Optional injectable
            :class:`~cadrumo.core._config_state_root.StateRootInputs` seam
            forwarded to :func:`_relative_path_anchor`. ``None`` (the
            default) captures the live process's inputs.

    Returns:
        The fully resolved absolute :class:`pathlib.Path`.
    """
    candidate = Path(value).expanduser()
    if not candidate.is_absolute():
        candidate = _relative_path_anchor(state_root_inputs) / candidate
    return _resolved_path(str(candidate))


@lru_cache(maxsize=4096)
def _resolved_path(path_text: str) -> Path:
    """Resolve one fully-composed path, memoised for the process.

    ``Path.resolve`` is a syscall, not a string operation: on Windows it
    walks every component through ``nt._getfinalpathname``, so resolving a
    28-field settings tree costs a few hundred kernel round trips. Nothing
    about that work varies with the caller -- the same composed path text
    resolves to the same location -- yet ``Settings`` re-derives every
    configured path on every construction, and a construction happens
    several times per operator action. One profile field edit measured 424
    ``_getfinalpathname`` calls, none of which could return a different
    answer than the call before it.

    The key is the composed path TEXT rather than the caller's argument, so
    the relative and absolute arms share one cache and a relative override
    cannot collide with a differently-anchored path of the same name.

    Memoising is safe against the case that actually occurs -- a configured
    directory resolved before it exists and created afterwards -- because a
    path's resolution does not change when it is created: measured on this
    platform across deep nesting, mixed case, and files. What DOES change a
    resolution is replacing a real directory with a symlink or junction
    pointing elsewhere, which is why :func:`clear_resolved_path_cache`
    exists and why any caller re-materialising a storage tree under a live
    process must call it.
    """
    return Path(path_text).resolve()


def clear_resolved_path_cache() -> None:
    """Drop memoised path resolutions after the filesystem moves underneath.

    Required only when a path already resolved during this process is made
    to resolve somewhere ELSE -- replacing a directory with a symlink or
    junction to a different target. Creating, deleting, or re-creating a
    directory at the same location does not change its resolution and needs
    no invalidation.

    This is the path-resolution counterpart of the engine and routed-settings
    invalidations a bucket re-materialisation already performs; a caller that
    swaps a storage root's identity beneath a running process calls all of
    them.
    """
    _resolved_path.cache_clear()


def normalize_project_relative_path(
    value: Path | None,
    *,
    state_root_inputs: StateRootInputs | None = None,
) -> Path | None:
    """Normalise an optional path setting to an absolute, data-root-anchored path.

    Used by settings validators for optional path fields. It preserves
    ``None`` and delegates path semantics to :func:`resolve_project_path`;
    it does not verify that the resulting path exists.

    Args:
        value: Optional configured path, or ``None``.
        state_root_inputs: Optional injectable
            :class:`~cadrumo.core._config_state_root.StateRootInputs` seam
            forwarded to :func:`resolve_project_path`. ``None`` (the
            default) captures the live process's inputs.

    Returns:
        ``None`` when ``value`` is ``None``; otherwise the resolved
        absolute path produced by :func:`resolve_project_path`.
    """
    if value is None:
        return None
    return resolve_project_path(value, state_root_inputs=state_root_inputs)


def effective_storage_root(
    root: Path | None = None,
    *,
    settings: Settings | None = None,
    state_root_inputs: StateRootInputs | None = None,
) -> Path:
    """Return the effective Cadrumo storage root: a caller override, or the settings default.

    The single accessor for the "an explicit root override wins, otherwise
    fall back to ``Settings.cadrumo_local_storage_root``" fallback that six
    call sites across ``application/user_profile`` and
    ``application/_config_reset_repository.py`` each re-implemented inline.
    Comparing the six copies surfaced real drift, not just duplication: one
    normalised an override by calling bare :meth:`~pathlib.Path.resolve`,
    which for a *relative* override resolves against the process's current
    working directory rather than anchoring it the way every other relative
    operator path in this codebase does; the other four returned an explicit
    override completely unnormalised — a relative override, or one carrying
    ``~``, passed straight through un-expanded and un-resolved. Both are
    defects: a login or profile-repository root must compare identically
    regardless of the directory the process happened to start from, and an
    unnormalised override risks a cross-platform identity mismatch (a
    differently-cased or non-canonical path failing to compare equal to
    itself resolved a second time elsewhere).

    An explicit ``root`` is therefore always normalised through
    :func:`resolve_project_path`: an absolute override resolves as-is
    (including Windows on-disk casing); a *relative* override anchors under
    the platform user-data root — one level above the settings default's own
    ``storage/`` — never under the current working directory and never
    nested under an already-derived storage root. ``root is None`` falls
    back to ``Settings.cadrumo_local_storage_root``, which the settings
    field validator already normalises identically on load, so no second
    resolve is spent on the common (no-override) path.

    Args:
        root: Optional caller-supplied storage-root override. ``None``
            (the default) resolves ``Settings.cadrumo_local_storage_root``.
        settings: Optional already-resolved
            :class:`~cadrumo.core.config.Settings`, read only when ``root``
            is ``None``, so a caller that already holds a ``Settings``
            instance need not trigger a second :func:`~cadrumo.core.config.load_settings`.
            ``None`` (the default) loads the live settings.
        state_root_inputs: Optional injectable
            :class:`~cadrumo.core._config_state_root.StateRootInputs` seam
            forwarded to :func:`resolve_project_path` when ``root`` is
            supplied. ``None`` (the default) captures the live process's
            inputs.

    Returns:
        The resolved absolute storage root.
    """
    if root is not None:
        return resolve_project_path(root, state_root_inputs=state_root_inputs)
    from .config import load_settings

    resolved_settings = settings if settings is not None else load_settings()
    return resolved_settings.cadrumo_local_storage_root


def resolve_relative_subpath(root: Path, relative_path: str, *, context: str) -> Path:
    """Resolve ``relative_path`` under ``root`` and enforce containment.

    The returned path is resolved and proven to stay under ``root`` after
    normalization. The helper performs no filesystem mutation and does not
    assert that the target exists; callers decide whether a missing file is
    valid for their operation.

    Args:
        root: The fixed parent directory that the result must live
            under.
        relative_path: A POSIX-style sub-path supplied by an
            untrusted-ish caller. Backslashes, absolute components,
            empty parts, ``.`` and ``..`` parts are all rejected.
        context: Short human-readable label used in raised error
            messages so the caller can attribute the failure.

    Returns:
        The resolved absolute path inside ``root``.

    Raises:
        CoreValidationError: When ``relative_path`` is malformed or
            when the resolved path escapes ``root``.
    """
    if "\\" in relative_path:
        raise CoreValidationError(f"{context} must use forward slashes only")
    pure = PurePosixPath(relative_path)
    if pure.is_absolute() or any(part in {"", ".", ".."} for part in pure.parts):
        raise CoreValidationError(f"{context} must stay within the owning root")

    resolved_root = root.resolve()
    resolved = (resolved_root / Path(*pure.parts)).resolve()
    try:
        resolved.relative_to(resolved_root)
    except ValueError as exc:
        raise CoreValidationError(f"{context} escapes the owning root") from exc
    return resolved


def file_stat_fingerprint(path: Path) -> tuple[str, int, int]:
    """Return a cache-key fingerprint triple for a single file.

    The triple ``(name, size_bytes, mtime_ns)`` is a stable, low-cost
    proxy for file identity used by file-backed loader caches. Any
    in-place modification that changes size or mtime invalidates the
    cache without requiring a full content hash.

    This is not an integrity hash or evidence digest. For byte-level
    verification use :func:`cadrumo.core.hashing.hash_file` or
    :func:`cadrumo.core.hashing.sha256_file`.

    Args:
        path: The file to fingerprint. Must be an existing, stat-able
            path.

    Returns:
        ``(path.name, stat.st_size, stat.st_mtime_ns)``. ``path.stat()``
        propagates ``OSError`` when the file is unreadable or disappears.
    """
    stat = path.stat()
    return (path.name, stat.st_size, stat.st_mtime_ns)


def path_stat_fingerprint(path: Path) -> tuple[str, int, int]:
    """Return a cache-key fingerprint triple for a single file, keyed by its full path.

    The path-keyed sibling of :func:`file_stat_fingerprint`. That function's
    triple starts with the bare file *name*, which is correct only when every
    candidate is known to come from the same directory (a tree-walk
    fingerprint); reused as a global cache key spanning multiple directories,
    a name-only first element collides across unrelated files that happen to
    share a filename. This triple starts with ``str(path)`` instead, so it
    stays unique across directories. Use :func:`file_stat_fingerprint` for a
    same-directory tree fingerprint (its shorter name-only key is the
    correct, and cheaper, choice there); use this one for a single-file
    loader cache keyed on a resolved, possibly cross-directory path.

    Args:
        path: The file to fingerprint. Must be an existing, stat-able
            path.

    Returns:
        ``(str(path), stat.st_size, stat.st_mtime_ns)``. ``path.stat()``
        propagates ``OSError`` when the file is unreadable or disappears.
    """
    stat = path.stat()
    return (str(path), stat.st_size, stat.st_mtime_ns)


def directory_byte_total(
    directory: Path,
    *,
    tolerate_errors: bool = False,
    entries: Iterable[Path] | None = None,
) -> tuple[int, int]:
    """Return ``(total_bytes, file_count)`` for every regular file under ``directory``.

    A missing (or not-a-directory) ``directory`` reports ``(0, 0)`` rather
    than raising, mirroring the shape every prior hand-rolled walker used.

    Args:
        directory: The directory to sum. Only used to short-circuit on
            absence when ``entries`` is not supplied; the actual walk reads
            ``entries`` (or a fresh recursive glob of ``directory``).
        tolerate_errors: When ``False`` (the default), an ``OSError`` raised
            while statting a candidate (or while advancing the recursive
            walk itself, e.g. a permission error on a subdirectory)
            propagates. When ``True``, the failing candidate — or the rest
            of an interrupted walk — is skipped and the total reflects only
            what was successfully stat'd, so a blob write racing this read
            never crashes the caller.
        entries: Pre-enumerated candidates to sum instead of a fresh
            ``directory.rglob("*")``. Injectable so a caller that already
            holds an enumeration can reuse it, and so a test can reproduce a
            file vanishing mid-walk deterministically (list the candidate,
            delete it on disk, then call this function with that stale
            reference).

    Returns:
        ``(total_bytes, file_count)`` summed over every regular file
        encountered. Directories and other non-regular entries among the
        candidates are silently skipped (not an error).
    """
    if entries is None and not directory.is_dir():
        return 0, 0
    candidates = iter(entries) if entries is not None else directory.rglob("*")
    total_bytes = 0
    file_count = 0
    while True:
        try:
            candidate = next(candidates)
        except StopIteration:
            break
        except OSError:
            if not tolerate_errors:
                raise
            break
        try:
            candidate_stat = candidate.stat()
        except OSError:
            if not tolerate_errors:
                raise
            continue
        if S_ISREG(candidate_stat.st_mode):
            total_bytes += candidate_stat.st_size
            file_count += 1
    return total_bytes, file_count


class _RetentionTimestamp(Protocol):
    """Any orderable retention timestamp: a ``datetime``, epoch ``float``, or ``int`` mtime_ns.

    The selector never compares timestamps produced by two different
    callers in the same call, so a consistent orderable representation per
    caller (rather than a single fixed type) is all this needs.
    """

    def __lt__(self, other: Any, /) -> bool: ...


def select_filesystem_retention_survivors[EntryT, TimestampT: _RetentionTimestamp](
    entries: Sequence[EntryT],
    *,
    timestamp: Callable[[EntryT], TimestampT],
    cutoff: TimestampT | None = None,
    max_count: int | None = None,
    max_total_bytes: int | None = None,
    size_fn: Callable[[EntryT], int] | None = None,
    combine: Literal["sequential", "union"] = "sequential",
    protect_newest: int = 0,
) -> tuple[list[EntryT], list[EntryT]]:
    """Select survivors/removals under composable age, count, and byte bounds.

    Mirrors :func:`~cadrumo.adapters.outbound.llm.select_retention_removal_keys`'s
    pure rank-and-bound shape, generalized to a filesystem entry (a run
    directory, a dump file, a telemetry file, a compiled-cache pickle)
    instead of a secure-object key, and widened from that primitive's fixed
    cutoff-then-count pipeline to composable, independently-optional bounds.
    Deletion stays with the caller: this function only decides who survives.

    Entries are ranked newest-first by ``timestamp`` (a stable sort, so
    entries sharing a timestamp keep their relative input order — pass
    entries pre-sorted by a secondary key when that tie-break matters, e.g.
    filename). ``protect_newest`` exempts the top-ranked N entries from
    removal under every bound, while still counting them toward the
    ``max_total_bytes`` running total and toward rank positions in
    ``combine="union"`` mode.

    Args:
        entries: Candidates to rank and select over. Order does not matter;
            the function re-ranks internally.
        timestamp: Projection returning each entry's retention timestamp.
        cutoff: Age boundary. An entry strictly older than ``cutoff`` is a
            removal candidate; an entry exactly at ``cutoff`` survives.
        max_count: Maximum surviving entries under the rank/count bound.
        max_total_bytes: Total-size ceiling; requires ``size_fn``. Oldest
            surviving entries are dropped until the running total fits.
        size_fn: Per-entry byte size, required when ``max_total_bytes`` is
            set.
        combine: ``"sequential"`` (default) applies ``cutoff``, then
            ``max_count``, then ``max_total_bytes`` as successive stages,
            each narrowing the previous stage's survivors — mirrors
            :func:`~cadrumo.adapters.outbound.llm.select_retention_removal_keys`'s
            cutoff-then-count shape, extended with a byte-total stage.
            ``"union"`` evaluates ``cutoff`` and ``max_count`` independently
            against the full (unstaged) ranking and removes an entry
            matching either — the shape a "keep the newest N sessions,
            otherwise prune by age or rank" policy needs, where a rank-3
            entry within the age window still gets removed for being beyond
            the count bound. ``"union"`` does not support
            ``max_total_bytes`` (a byte ceiling has no rank-independent
            per-entry membership test).
        protect_newest: The top-ranked N entries survive unconditionally
            (still counted toward ``max_total_bytes`` and toward rank
            positions in ``"union"`` mode).

    Returns:
        ``(keep, remove)``, both drawn from ``entries`` with no entry in
        both.

    Raises:
        ValueError: When no bound is supplied, when ``max_total_bytes`` is
            supplied without ``size_fn``, or when ``combine="union"`` is
            paired with ``max_total_bytes``.
    """
    if cutoff is None and max_count is None and max_total_bytes is None:
        raise ValueError(
            "select_filesystem_retention_survivors requires at least one of cutoff, max_count, max_total_bytes",
        )
    if max_total_bytes is not None and size_fn is None:
        raise ValueError("max_total_bytes requires size_fn")
    if combine == "union" and max_total_bytes is not None:
        raise ValueError("combine='union' does not support max_total_bytes")

    ranked: list[tuple[int, EntryT]] = sorted(
        enumerate(entries),
        key=lambda pair: timestamp(pair[1]),
        reverse=True,
    )
    protected_indices = {index for index, _entry in ranked[: max(protect_newest, 0)]}

    if combine == "union":
        keep_pairs: list[tuple[int, EntryT]] = []
        remove_pairs: list[tuple[int, EntryT]] = []
        for rank, (index, entry) in enumerate(ranked):
            if index in protected_indices:
                keep_pairs.append((index, entry))
                continue
            expired = cutoff is not None and timestamp(entry) < cutoff
            beyond_rank = max_count is not None and rank >= max_count
            (remove_pairs if (expired or beyond_rank) else keep_pairs).append((index, entry))
        return [entry for _, entry in keep_pairs], [entry for _, entry in remove_pairs]

    survivors = ranked
    removed: list[tuple[int, EntryT]] = []

    if cutoff is not None:
        kept, expired_pairs = [], []
        for index, entry in survivors:
            if index not in protected_indices and timestamp(entry) < cutoff:
                expired_pairs.append((index, entry))
            else:
                kept.append((index, entry))
        survivors, removed = kept, removed + expired_pairs

    if max_count is not None:
        kept, excess_pairs = [], []
        retained = 0
        for index, entry in survivors:
            if index in protected_indices:
                kept.append((index, entry))
                continue
            if retained < max_count:
                kept.append((index, entry))
                retained += 1
            else:
                excess_pairs.append((index, entry))
        survivors, removed = kept, removed + excess_pairs

    if max_total_bytes is not None:
        assert size_fn is not None  # enforced above
        total = sum(size_fn(entry) for _index, entry in survivors)
        over_ceiling: list[tuple[int, EntryT]] = []
        over_indices: set[int] = set()
        for index, entry in reversed(survivors):  # oldest surviving entry first
            if total <= max_total_bytes:
                break
            if index in protected_indices:
                continue
            over_ceiling.append((index, entry))
            over_indices.add(index)
            total -= size_fn(entry)
        survivors = [pair for pair in survivors if pair[0] not in over_indices]
        removed = removed + over_ceiling

    return [entry for _index, entry in survivors], [entry for _index, entry in removed]
