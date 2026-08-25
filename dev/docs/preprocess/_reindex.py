"""Reindex-before-sweep pipeline step and index-coverage inspection.

The build-time RAG sweep (the compilation oracle) is only as good as the
index it queries, and the resident service's filesystem watcher can MISS
newly-written files (the documented staleness hole: extraction sidecars are
written in bulk and the watcher's scoped incremental does not always catch
them). This module is the mandated pre-sweep step that closes that hole: it
runs an explicit incremental code reindex through the resident service, then
exposes a coverage check that compares the files the walker WOULD index
against the files actually present in the index metadata.

Routing rule: the reindex is delegated to the running service on the shared
port (``--port 8766``); the local-file Qdrant store is single-writer, so a
competing in-process index would strand on the lock. The sweep step calls
``run_incremental_reindex`` first, then proceeds only once the index is
current.

The coverage check is deliberately deterministic and offline: it reads the
on-disk ``code_index_meta.json`` and reuses the installed walker's own
``CodebaseIndexer.scan_files`` to compute the expected set, so it applies the
exact gitignore / ``.vaultragignore`` / extension / size / binary filters the
real index applies - including any ``.vaultragignore`` exclusion (a raw
surface deliberately dropped in favour of its extraction sidecar is then
legitimately absent, never a false gap).
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Final

from ..._paths import UTF_8

#: Default port of the resident vaultspec-rag service (the single-writer
#: store). Every reindex/search routes here so jobs serialise through the
#: service rather than competing for the Qdrant lock.
RAG_SERVICE_PORT = 8766
_UTF_8: Final[str] = UTF_8

#: Path, relative to the repo root, of the code index content-hash metadata
#: the walker writes after each index run.
_META_RELPATH = Path(".vault/data/search-data/code_index_meta.json")

#: The corpus subtree whose coverage the docs-search pipeline depends on.
_DATA_RELROOT = "src/cadrumo/_data"


class ReindexError(RuntimeError):
    """Raised when the incremental reindex command fails."""


def run_incremental_reindex(
    repo_root: Path,
    *,
    port: int = RAG_SERVICE_PORT,
    timeout_s: float = 1800.0,
) -> str:
    """Run an explicit incremental code reindex through the resident service.

    This is the mandated pre-sweep step: the query-vocabulary sweep MUST call
    this first so the index reflects every freshly-written sidecar before any
    query runs. The reindex is delegated to the service on ``port`` (the
    single-writer store); a bare incremental index (no ``--rebuild``) is safe
    and proportional to the change set.

    Args:
        repo_root: Repository root the command runs from.
        port: Service port to delegate to.
        timeout_s: Hard timeout for the queued job to be accepted.

    Returns:
        The command's stdout (the job-queued acknowledgement).

    Raises:
        ReindexError: If the command exits non-zero.
    """
    cmd = [
        "uv",
        "run",
        "--no-sync",
        "vaultspec-rag",
        "index",
        "--type",
        "code",
        "--port",
        str(port),
    ]
    # The command is a fixed literal argv (no shell, no untrusted input); the
    # only variable is the integer port rendered via str() - hence the S603
    # suppression on the call below.
    result = subprocess.run(  # noqa: S603
        cmd,
        cwd=repo_root,
        capture_output=True,
        text=True,
        timeout=timeout_s,
        check=False,
    )
    if result.returncode != 0:
        detail = result.stderr.strip() or result.stdout.strip()
        raise ReindexError(f"incremental reindex failed (exit {result.returncode}): {detail}")
    return result.stdout


def load_index_meta(repo_root: Path) -> dict[str, str]:
    """Load the code index content-hash metadata as a path -> hash mapping.

    Args:
        repo_root: Repository root.

    Returns:
        The metadata mapping (POSIX-relative path -> blake2b hex), or an
        empty mapping when the file is absent or unparseable.
    """
    meta_path = repo_root / _META_RELPATH
    if not meta_path.is_file():
        return {}
    try:
        data = json.loads(meta_path.read_text(encoding=_UTF_8))
    except (OSError, json.JSONDecodeError):
        return {}
    if not isinstance(data, dict):
        return {}
    return {str(k): str(v) for k, v in data.items()}


def expected_data_files(repo_root: Path) -> set[str]:
    """Return the POSIX-relative ``_data`` files the walker would index.

    Reuses the installed ``CodebaseIndexer.scan_files`` so the gitignore /
    ``.vaultragignore`` / extension / size / binary filters are applied
    exactly as the real index applies them - in particular, a raw surface
    excluded via ``.vaultragignore`` (in favour of its extraction sidecar) is
    not in this set, so the coverage check treats it as legitimately absent.

    ``scan_files`` stops at those filters, one step short of the indexer's
    admission policy: a zero-byte source yields no chunks and the indexer
    converges it as ``SOURCE_EMPTY`` (an admission rejection, recorded and
    never retried), so it never earns a ``code_index_meta.json`` entry no
    matter how often the reindex runs. Such a file is therefore dropped here
    too - keeping it would make the coverage gate permanently and
    unfixably red on, for example, an empty package ``__init__.py``.

    Args:
        repo_root: Repository root.

    Returns:
        The set of POSIX-relative paths under ``src/cadrumo/_data`` the walker
        would index.
    """
    from vaultspec_rag.indexer._codebase_indexer import CodebaseIndexer

    # scan_files() needs neither model nor store (its docstring states it is
    # safe with model=None/store=None for dry-run use); the __init__ signature
    # types them as required, so the None pass is a documented boundary escape.
    indexer = CodebaseIndexer(
        root_dir=repo_root,
        model=None,  # ty: ignore[invalid-argument-type]  # reason: scan_files() is model-free per its docstring
        store=None,  # ty: ignore[invalid-argument-type]  # reason: scan_files() is store-free per its docstring
    )
    scanned = indexer.scan_files()
    data_prefix = f"{_DATA_RELROOT}/"
    expected: set[str] = set()
    for path in scanned:
        resolved = path.resolve()
        rel = resolved.relative_to(repo_root.resolve()).as_posix()
        if not rel.startswith(data_prefix):
            continue
        if resolved.is_file() and resolved.stat().st_size == 0:
            continue
        expected.add(rel)
    return expected


def missing_data_files(repo_root: Path) -> set[str]:
    """Return ``_data`` files the walker would index but are NOT in the index.

    The coverage gate: an empty result means every walker-indexable ``_data``
    file (every extraction sidecar plus the natively-supported corpus files)
    is present in the index metadata. A non-empty result is the staleness
    hole surfacing - the sweep must not run until it is empty.

    Args:
        repo_root: Repository root.

    Returns:
        The set of expected-but-absent POSIX-relative paths.
    """
    expected = expected_data_files(repo_root)
    indexed = set(load_index_meta(repo_root))
    return expected - indexed
