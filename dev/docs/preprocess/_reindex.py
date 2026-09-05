"""Reindex-before-sweep pipeline step.

The build-time RAG sweep (the compilation oracle) is only as good as the
index it queries, and the resident service's filesystem watcher can MISS
newly-written files: extraction sidecars are written in bulk and the
watcher's scoped incremental does not always catch them. This module is the
mandated pre-sweep step that closes that hole, running an explicit
incremental code reindex through the resident service.

Routing rule: the reindex is delegated to the running service on the shared
port (``--port 8766``); the local-file Qdrant store is single-writer, so a
competing in-process index would strand on the lock. The sweep step calls
``run_incremental_reindex`` first, then proceeds only once the index is
current.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

#: Default port of the resident vaultspec-rag service (the single-writer
#: store). Every reindex/search routes here so jobs serialise through the
#: service rather than competing for the Qdrant lock.
RAG_SERVICE_PORT = 8766


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
