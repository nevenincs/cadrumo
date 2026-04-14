"""Deterministic SHA-256 fingerprints of corpus, db, and certificate state.

Used by the observability layer to gate dry-run replay. See ADR D5 for
the rationale (auditability over time-travel) and the research doc for
the precise hash inputs.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

from aeat.config import Settings


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

    Args:
        root: Directory to walk.
        excluded_dirs: Absolute paths whose entire subtree must be skipped.

    Returns:
        SHA-256 hex digest of the canonical ``rel_path|sha256\\n``
        rendering. Empty tree hashes to the digest of the empty string.
    """
    if not root.exists():
        return hashlib.sha256(b"").hexdigest()
    entries: list[tuple[str, str]] = []
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        if any(excluded.exists() and excluded in path.parents for excluded in excluded_dirs):
            continue
        rel = path.relative_to(root).as_posix()
        entries.append((rel, _file_sha256(path)))
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

    Excludes ``var/runs/`` (self-reference) and ``var/browser-traces/``
    (Playwright noise) so the hash is stable across observability writes.

    Args:
        var_dir: Path to the local ``var/`` directory.

    Returns:
        SHA-256 hex digest of the curated tree.
    """
    excluded = frozenset(
        {
            (var_dir / "runs").resolve(),
            (var_dir / "browser-traces").resolve(),
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
