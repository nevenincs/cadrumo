"""Deterministic SHA-256 fingerprints of corpus, db, and certificate state.

Used by :func:`run_context` to stamp a recorded :class:`RunTrace` and
by :func:`replay_run` to gate read-only replay. A replay refuses when
any recorded hash has drifted relative to the current on-disk state.

Auditability is prioritised over time-travel: a drift refusal forces
the operator to acknowledge the change rather than silently re-running
a recorded command against a moved-on environment.

``db_sha256`` fingerprints :attr:`~cadrumo.core.config.Settings.cadrumo_local_storage_root`
— the single canonical application data root every persisted category
(encrypted state, caches, durable generated outputs) derives from, per
:class:`~cadrumo.core.config.Settings` and
:mod:`cadrumo.core._config_state_root`. This is deliberate: on an
installed distribution the historical ``REPO_ROOT / "var"`` location
resolves inside the virtualenv or the packaging tool's ephemeral cache
and typically does not exist, which previously made ``db_sha256``
degrade to the constant empty-tree digest for every installed operator
and permanently defeat drift detection rather than merely reporting "no
state yet" once.
"""

from __future__ import annotations

import hashlib
import os
import time
from pathlib import Path

from ..config import Settings, load_settings
from ..hashing import sha256_file, sha256_hex
from ..logging import get_logger

_log = get_logger(__name__)


def _file_sha256(path: Path) -> str:
    """Return the SHA-256 hex digest of a file's contents."""
    last_error: PermissionError | None = None
    for attempt in range(5):
        try:
            return sha256_file(path)
        except PermissionError as exc:
            last_error = exc
            if attempt == 4:
                break
            time.sleep(0.05)
    assert last_error is not None
    raise last_error


def _hash_tree(
    root: Path,
    *,
    excluded_dirs: frozenset[Path],
) -> str:
    r"""Hash a directory tree as a sorted list of ``(rel_path, sha256)`` pairs.

    Uses :func:`os.walk` with top-down directory pruning so excluded
    subtrees are never descended — on a workstation with tens of GB
    of LLM and status cache data under ``var/`` this is orders of magnitude
    faster than walking everything and filtering after the fact.

    Args:
        root: Directory to walk.
        excluded_dirs: Resolved absolute paths whose entire subtree
            must be skipped. Each entry is compared against the
            resolved path of a visited directory; matching directories
            are pruned from ``dirnames`` before descent.

    Returns:
        SHA-256 hex digest of the canonical ``rel_path|sha256\\n``
        rendering. Empty tree hashes to the digest of the empty string.
    """
    if not root.exists():
        return sha256_hex(b"")
    entries: list[tuple[str, str]] = []
    for dirpath, dirnames, filenames in os.walk(root):
        dir_path = Path(dirpath)
        # Prune excluded subtrees in place — the mutation is documented
        # behaviour of :func:`os.walk` when ``topdown=True`` (default).
        dirnames[:] = [name for name in dirnames if (dir_path / name).resolve() not in excluded_dirs]
        for fname in filenames:
            file_path = dir_path / fname
            try:
                rel = file_path.relative_to(root).as_posix()
            except ValueError as rel_exc:
                _log.debug(
                    "observability fingerprint: skipping %s — not under root %s (%s)",
                    file_path,
                    root,
                    rel_exc,
                )
                continue
            try:
                sha = _file_sha256(file_path)
            except OSError as exc:
                _log.debug(
                    "observability fingerprint: marking %s unreadable (%s)",
                    file_path,
                    exc,
                )
                sha = f"unreadable:{type(exc).__name__}:{getattr(exc, 'errno', '')}"
            entries.append((rel, sha))
    entries.sort()
    digest = hashlib.sha256()
    for rel, sha in entries:
        digest.update(rel.encode("utf-8"))
        digest.update(b"|")
        digest.update(sha.encode("ascii"))
        digest.update(b"\n")
    return digest.hexdigest()


def compute_corpus_sha256(settings: Settings) -> str:
    """Compute a deterministic fingerprint of the effective configuration.

    Hashes ``settings.model_dump_json()`` — the currently-loaded
    :class:`Settings` snapshot, which already folds every
    environment-variable-sourced override. Production ``Settings`` carries
    no dotenv source of its own (see
    :meth:`~cadrumo.core.config.Settings.settings_customise_sources`): an
    operator's ``env/.env`` is development/test-only configuration bridged
    into the process environment before ``Settings`` resolves, so its
    values are already reflected in the snapshot hashed here and it needs
    no separate hashing channel.

    Args:
        settings: Active :class:`Settings` instance to fingerprint.

    Returns:
        SHA-256 hex digest of the Settings snapshot.
    """
    return sha256_hex(settings.model_dump_json().encode("utf-8"))


def compute_db_sha256(root: Path, *, excluded_dirs: frozenset[Path] = frozenset()) -> str:
    """Compute a deterministic fingerprint of a directory tree.

    A generic, domain-agnostic content-addressed directory hash. Two
    callers use it for different purposes: :func:`compute_data_root_sha256`
    fingerprints the live application data root with the exclusion set
    :func:`data_root_cache_exclusions` computes from :class:`Settings`,
    and a determinism-conformance test fingerprints an arbitrary snapshot
    directory of committed database files with no exclusions at all. This
    function itself knows nothing about ``Settings`` or the storage-root
    taxonomy.

    Args:
        root: Directory to walk.
        excluded_dirs: Absolute or relative paths whose entire subtree is
            skipped; resolved internally before comparison so callers may
            pass either form.

    Returns:
        SHA-256 hex digest of the curated tree.
    """
    resolved_excluded = frozenset(path.resolve() for path in excluded_dirs)
    return _hash_tree(root, excluded_dirs=resolved_excluded)


def data_root_cache_exclusions(settings: Settings) -> frozenset[Path]:
    """Return the regenerable/self-referential directories under the data root.

    Every entry here is read from ``settings`` itself — the same instance
    whose :attr:`~cadrumo.core.config.Settings.cadrumo_local_storage_root`
    :func:`compute_data_root_sha256` hashes — rather than a hardcoded
    subpath string, so an operator override of any one of these
    directories (e.g. a redirected LLM cache) is still excluded correctly
    regardless of where it actually resolves:

    - ``cadrumo_runs_dir`` — observability's own output (self-reference);
      hashing it would make every run's ``db_sha256`` depend on the
      immediately preceding run's trace files.
    - ``cadrumo_llm_cache_dir``, ``cadrumo_llm_usage_dir``,
      ``cadrumo_llm_run_telemetry_dir`` — LLM prompt cache, usage meters,
      and run-timing telemetry; these drift on every model call and carry
      no taxpayer state.
    - ``cadrumo_status_cache_dir`` — AEAT status-reader cache.
    - ``cadrumo_corpus_text_cache_dir``, ``cadrumo_validation_verdict_cache_dir``
      — regenerable, evictable caches unrelated to real taxpayer state.
    - ``cadrumo_storage_backup_dir`` — storage-layer backups (non-canonical
      copies of state already fingerprinted at its primary location).

    Core state (the encrypted profile/bucket database, ``workflow-runs``,
    ``inbox``, ``drafts``, ``filing-history``, ``justificantes``,
    ``financial/*``) is deliberately absent from this set: changes there
    are real state drift that a replay must detect.
    """
    return frozenset(
        path.resolve()
        for path in (
            settings.cadrumo_runs_dir,
            settings.cadrumo_llm_cache_dir,
            settings.cadrumo_llm_usage_dir,
            settings.cadrumo_llm_run_telemetry_dir,
            settings.cadrumo_status_cache_dir,
            settings.cadrumo_corpus_text_cache_dir,
            settings.cadrumo_validation_verdict_cache_dir,
            settings.cadrumo_storage_backup_dir,
        )
    )


def compute_data_root_sha256(settings: Settings) -> str:
    """Compute :func:`compute_db_sha256` over the canonical application data root.

    Hashes ``settings.cadrumo_local_storage_root`` — the single root every
    persisted category (encrypted state, caches, durable generated
    outputs) derives from in both a source checkout
    (``REPO_ROOT/var/storage``) and an installed distribution (the
    platform user-data directory) — excluding the regenerable caches and
    observability's own output via :func:`data_root_cache_exclusions`.

    A data root that does not exist yet (a pristine install with no
    profile created) hashes to the same digest as an empty tree: this is
    a legitimate, expected, self-resolving state (it disappears the
    moment any state is written) rather than the historical defect, where
    a *wrong* root was hashed unconditionally on every installed run and
    every operator's ``db_sha256`` stayed the empty-tree constant forever,
    permanently defeating drift detection. A missing root is logged at
    debug level so the condition remains traceable without being
    disruptive on an otherwise-successful first invocation.

    Args:
        settings: Active :class:`Settings` instance supplying both the
            root to hash and the exclusions to apply.

    Returns:
        SHA-256 hex digest of the curated application data root.
    """
    root = settings.cadrumo_local_storage_root
    if not root.exists():
        _log.debug(
            "observability fingerprint: cadrumo_local_storage_root %s does not exist yet "
            "(no profile/state created); hashing as an empty tree",
            root,
        )
    return compute_db_sha256(root, excluded_dirs=data_root_cache_exclusions(settings))


def read_cert_fingerprint() -> str:
    """Return the SHA-256 fingerprint of the active certificate, or ``""``.

    The empty string is the canonical "no certificate bound" sentinel —
    most CLI paths run without a cert (lookups, planning, replay) and
    must still produce a valid :class:`RunTrace`.

    Reading the certificate without unlocking it is intentional: the
    observability layer never asks the operator for a passphrase, so
    we hash whatever DER bytes are visible on disk. When no path is
    configured we return ``""``.
    """
    # `load_settings()` honours `override_settings`; bare `Settings()`
    # bypasses the context-var so a test that overrides the cert path
    # sees the project-default fingerprint instead of its own.
    settings = load_settings()
    cert_path = settings.cadrumo_certificate_path
    if cert_path is None or not cert_path.exists():
        return ""
    return _file_sha256(cert_path)


__all__ = [
    "compute_corpus_sha256",
    "compute_data_root_sha256",
    "compute_db_sha256",
    "data_root_cache_exclusions",
    "read_cert_fingerprint",
]
