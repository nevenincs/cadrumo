"""Deterministic SHA-256 fingerprints of corpus, db, and certificate state.

Used by :func:`run_context` to stamp a recorded :class:`RunTrace` and
by :func:`replay_run` to gate read-only replay. A replay refuses when
any recorded hash has drifted relative to the current on-disk state.

Auditability is prioritised over time-travel: a drift refusal forces
the operator to acknowledge the change rather than silently re-running
a recorded command against a moved-on environment.
"""

from __future__ import annotations

import hashlib
import os
import time
from pathlib import Path

from ..config import Settings, load_settings
from ..hashing import sha256_hex
from ..logging import get_logger

_log = get_logger(__name__)


def _file_sha256(path: Path) -> str:
    """Return the SHA-256 hex digest of a file's contents."""
    last_error: PermissionError | None = None
    for attempt in range(5):
        try:
            h = hashlib.sha256()
            with path.open("rb") as handle:
                for chunk in iter(lambda: handle.read(65536), b""):
                    h.update(chunk)
            return h.hexdigest()
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


def compute_corpus_sha256(
    vault_dir: Path,
    settings: Settings,
    *,
    env_path: Path | None = None,
) -> str:
    """Compute a deterministic fingerprint of ``.vault/`` plus Settings plus the on-disk ``.env``.

    The hash folds three inputs so replay's drift gate catches every
    channel that can change the effective configuration between record
    and replay:

    1. The ``.vault/`` spec content — architectural decisions, plans,
       research, execution records. ``.vault/data/`` is excluded:
       it hosts the gitignored vaultspec-rag index (Qdrant database
       files, embeddings cache) which mutates continuously under a
       live RAG service and is not part of the canonical spec surface
       a replay needs to gate on.
    2. ``settings.model_dump_json()`` — the currently-loaded Settings
       snapshot (includes env-var-sourced overrides).
    3. The raw bytes of ``env/.env`` if present — catches dotfile
       edits the operator made after process start that won't be
       reflected in the already-instantiated ``Settings()``.

    Combining (2) + (3) is deliberate: (2) alone misses post-startup
    ``.env`` edits; (3) alone misses shell-exported env vars and
    test-fixture overrides. Together they close the drift hole.

    Args:
        vault_dir: Path to the ``.vault/`` directory.
        settings: Active :class:`Settings` instance to fold into the hash.
        env_path: Path to the ``.env`` dotfile. Defaults to
            ``PROJECT_ROOT/env/.env``; passed explicitly by tests so the
            dotfile channel can be exercised against a temp file without
            patching the ``PROJECT_ROOT`` module constant.

    Returns:
        SHA-256 hex digest of the vault tree + Settings snapshot +
        ``.env`` bytes tuple.
    """
    from ..config import PROJECT_ROOT

    excluded_vault_subtrees = frozenset({(vault_dir / "data").resolve()})
    tree_digest = _hash_tree(vault_dir, excluded_dirs=excluded_vault_subtrees)
    settings_blob = settings.model_dump_json().encode("utf-8")
    resolved_env_path = env_path if env_path is not None else PROJECT_ROOT / "env" / ".env"
    env_digest = _file_sha256(resolved_env_path) if resolved_env_path.exists() else sha256_hex(b"")
    h = hashlib.sha256()
    h.update(tree_digest.encode("ascii"))
    h.update(b"|settings|")
    h.update(sha256_hex(settings_blob).encode("ascii"))
    h.update(b"|env|")
    h.update(env_digest.encode("ascii"))
    return h.hexdigest()


def compute_db_sha256(var_dir: Path) -> str:
    """Compute a deterministic fingerprint of the local ``var/`` state.

    Excludes caches, build artefacts, and self-referencing observability
    outputs so the hash is stable across observability writes and
    LLM/status lookups that would otherwise flap on every read.
    The curated list covers every ``var/`` subdirectory that
    :class:`aeat.core.config.Settings` treats as a cache, log, or
    replay-internal artefact, plus every ``var/`` subdirectory the
    release / packaging pipeline materialises as a transient virtualenv:

    - ``var/runs/`` — observability's own output (self-reference).
    - ``var/browser-traces/`` — Playwright session traces.
    - ``var/llm-cache/``, ``var/llm-usage/`` — LLM prompt cache + usage
      meters; drift on every model call.
    - ``var/status-cache/`` — AEAT status-reader cache.
    - ``var/backups/`` — storage layer backups (non-canonical copies).
    - ``var/packaging-smoke/``, ``var/editable-smoke/`` — release
      pipeline scratch virtualenvs (thousands of site-packages files).
    - ``var/divergences/``, ``var/i18n/`` — release / i18n diff
      artefacts; not part of the user-state surface.

    Core state (``var/aeat.db``, ``var/workflow-runs/``, ``var/inbox/``,
    ``var/drafts/``, ``var/filing-history/``, ``var/justificantes/``)
    is included because changes there represent real state drift that
    a replay must detect.

    Args:
        var_dir: Path to the local ``var/`` directory.

    Returns:
        SHA-256 hex digest of the curated tree.
    """
    excluded = frozenset(
        {
            (var_dir / name).resolve()
            for name in (
                "runs",
                "browser-traces",
                "llm-cache",
                "llm-usage",
                "status-cache",
                "backups",
                "packaging-smoke",
                "editable-smoke",
                "divergences",
                "i18n",
            )
        },
    )
    return _hash_tree(var_dir, excluded_dirs=excluded)


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
    cert_path = settings.aeat_certificate_path
    if cert_path is None or not cert_path.exists():
        return ""
    return _file_sha256(cert_path)


__all__ = [
    "compute_corpus_sha256",
    "compute_db_sha256",
    "read_cert_fingerprint",
]
