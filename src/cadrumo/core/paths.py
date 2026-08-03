"""Shared path normalization and containment helpers.

Centralises the small set of :class:`~pathlib.Path` primitives that every other
``aeat`` module needs: resolving repo-relative paths against a RunMode-aware
anchor via :func:`resolve_project_path`, normalising user-provided settings
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
from pathlib import Path, PurePosixPath

from ._config_state_root import (
    RunMode,
    StateRootInputs,
    detect_run_mode,
    live_state_root_inputs,
    platform_user_data_root,
)
from .errors import CoreValidationError


def _relative_path_anchor(state_root_inputs: StateRootInputs | None = None) -> Path:
    """Return the RunMode-aware base for resolving a relative operator path.

    Sourced entirely from the application-data-root authority in
    :mod:`cadrumo.core._config_state_root` — never from the local
    repo-root walk. A source checkout anchors at
    ``inputs.project_root_candidate`` (the checkout-root candidate the
    state-root authority already computes). An installed distribution
    anchors under the platform user-data directory
    (:func:`cadrumo.core._config_state_root.platform_user_data_root`)
    instead, so a relative override of a ``var/``-style operator setting
    (storage root, cache dir, log dir, financial catalogue dir, ...) can
    never resolve inside a virtualenv or an ephemeral package cache — the
    same hazard :func:`cadrumo.core._config_state_root.resolve_state_root`
    already closes for the ``cadrumo_local_storage_root`` default.

    Args:
        state_root_inputs: Injectable :class:`~cadrumo.core._config_state_root.StateRootInputs`
            seam. ``None`` (the live default) captures the running process's
            inputs via :func:`~cadrumo.core._config_state_root.live_state_root_inputs`
            — the same seam :func:`~cadrumo.core._config_state_root.default_storage_root`
            reads, so a relative override and the unset default resolve
            consistently. Tests inject a deterministic ``installed`` or
            ``checkout`` context without mutating the ambient process.
    """
    inputs = state_root_inputs if state_root_inputs is not None else live_state_root_inputs()
    if detect_run_mode(inputs) is RunMode.CHECKOUT:
        return inputs.project_root_candidate
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
#: the bucket-directory layout can append below a configured storage root:
#: ``\buckets\<uuid-36>\blobs\<hmac-8>--<label-64>.meta.json``. Mirrors
#: :data:`cadrumo.adapters.persistence.storage._namespace_registry.BUCKETS_DIRNAME`
#: / ``BUCKET_BLOBS_DIRNAME`` and the outbound
#: ``LocalFileSystemProvider`` filename shape
#: (``<hmac_prefix_8>--<label>.meta.json``, ``label`` capped at 64 chars).
#: Kept as a literal here (not imported) because this module sits below the
#: persistence and outbound-storage layers in the dependency graph; the
#: two call sites that use this constant assert their real deepest-suffix
#: shapes against it in tests.
WINDOWS_WORST_CASE_OBJECT_PATH_SUFFIX_LENGTH: int = len(
    "\\buckets\\" + ("0" * 36) + "\\blobs\\" + ("a" * 8) + "--" + ("b" * 64) + ".meta.json",
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
    """Resolve a relative path against the RunMode-aware anchor.

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
            default) resolves the live process's RunMode.

    Returns:
        The fully resolved absolute :class:`pathlib.Path`.
    """
    candidate = Path(value).expanduser()
    if candidate.is_absolute():
        return candidate.resolve()
    return (_relative_path_anchor(state_root_inputs) / candidate).resolve()


def normalize_project_relative_path(
    value: Path | None,
    *,
    state_root_inputs: StateRootInputs | None = None,
) -> Path | None:
    """Normalise an optional path setting to an absolute, RunMode-anchored path.

    Used by settings validators for optional path fields. It preserves
    ``None`` and delegates path semantics to :func:`resolve_project_path`;
    it does not verify that the resulting path exists.

    Args:
        value: Optional configured path, or ``None``.
        state_root_inputs: Optional injectable
            :class:`~cadrumo.core._config_state_root.StateRootInputs` seam
            forwarded to :func:`resolve_project_path`. ``None`` (the
            default) resolves the live process's RunMode.

    Returns:
        ``None`` when ``value`` is ``None``; otherwise the resolved
        absolute path produced by :func:`resolve_project_path`.
    """
    if value is None:
        return None
    return resolve_project_path(value, state_root_inputs=state_root_inputs)


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
