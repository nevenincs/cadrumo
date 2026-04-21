"""Deterministic SHA-256 fingerprints of corpus, db, and certificate state.

Used by the observability layer to gate dry-run replay. See ADR D5 for
the rationale (auditability over time-travel) and the research doc for
the precise hash inputs.
"""

from __future__ import annotations

import hashlib
import os
from pathlib import Path

from ..config import Settings


def _file_sha256(path: Path) -> str:
    """Return the SHA-256 hex digest of a file's contents."""
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _hash_tree(
    root: Path,
    *,
    excluded_dirs: frozenset[Path],
) -> str:
    """Hash a directory tree as a sorted list of ``(rel_path, sha256)`` pairs.

    Uses :func:`os.walk` with top-down directory pruning so excluded
    subtrees are never descended — on a workstation with tens of GB
    of LLM / schema cache under ``var/`` this is orders of magnitude
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
        return hashlib.sha256(b"").hexdigest()
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
            except ValueError:
                continue
            entries.append((rel, _file_sha256(file_path)))
    entries.sort()
    digest = hashlib.sha256()
    for rel, sha in entries:
        digest.update(rel.encode("utf-8"))
        digest.update(b"|")
        digest.update(sha.encode("ascii"))
        digest.update(b"\n")
    return digest.hexdigest()


def compute_corpus_sha256(vault_dir: Path, settings: Settings) -> str:
    """Compute a deterministic fingerprint of ``.vault/`` plus Settings.

    Args:
        vault_dir: Path to the ``.vault/`` directory.
        settings: Active :class:`Settings` instance to fold into the hash.

    Returns:
        SHA-256 hex digest of the corpus + serialized settings tuple.
    """
    tree_digest = _hash_tree(vault_dir, excluded_dirs=frozenset())
    settings_blob = settings.model_dump_json().encode("utf-8")
    h = hashlib.sha256()
    h.update(tree_digest.encode("ascii"))
    h.update(b"|settings|")
    h.update(hashlib.sha256(settings_blob).hexdigest().encode("ascii"))
    return h.hexdigest()


def compute_db_sha256(var_dir: Path) -> str:
    """Compute a deterministic fingerprint of the local ``var/`` state.

    Excludes caches and self-referencing artefacts so the hash is
    stable across observability writes and LLM/schema/status lookups
    that would otherwise flap on every read. The curated list covers
    every ``var/`` subdirectory that :class:`aeat.config.Settings`
    treats as a cache, log, or replay-internal artefact:

    - ``var/runs/`` — observability's own output (self-reference).
    - ``var/browser-traces/`` — Playwright session traces.
    - ``var/llm-cache/``, ``var/llm-usage/`` — LLM prompt cache + usage
      meters; drift on every model call.
    - ``var/schema-cache/`` — derived Modelo schema cache.
    - ``var/status-cache/`` — AEAT status-reader cache.
    - ``var/backups/`` — storage layer backups (non-canonical copies).

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
                "schema-cache",
                "status-cache",
                "backups",
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
    settings = Settings()
    cert_path = settings.aeat_certificate_path
    if cert_path is None or not cert_path.exists():
        return ""
    return _file_sha256(cert_path)


__all__ = [
    "compute_corpus_sha256",
    "compute_db_sha256",
    "read_cert_fingerprint",
]
