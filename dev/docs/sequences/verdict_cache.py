"""Reuse a clean cli-sequence gate verdict when nothing it depends on has changed.

The gate executes every documented CLI sequence against the real CLI and
compares the transcripts with their committed goldens. Its verdict is a pure
function of the product source (the CLI, its registry data and the golden mask
set), the gate engine, the sequence contracts, goldens, seeds and fixtures, the
directives the pages enroll, the published registry authority, the locked
dependencies and the interpreter. The key hashes all of them, enumerated from
the filesystem, so any change to any input is a cache miss and a re-run.

Only a clean verdict is stored. A divergence is never cached, so a cache can
cost a re-run but can never turn a failing gate green; a hit always says which
recorded verdict it reused.
"""

from __future__ import annotations

import hashlib
import json
import os
import platform
import re
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Final, Protocol

from cadrumo.core.directory_scan import DirectoryEntryKind, scan_directory
from dev._paths import REPO_ROOT
from dev.cache_root import dev_cache_dir

#: Set to bypass the cache and always execute the gate.
FORCE_ENV: Final[str] = "CADRUMO_DOCS_FORCE_SEQUENCE_CHECK"
_CACHE_NAME: Final[str] = "docs-sequence-verdicts"
_DIRECTIVE_RE: Final[re.Pattern[str]] = re.compile(r"^```\{cli-sequence\}.*?^```", re.MULTILINE | re.DOTALL)
_PRUNED: Final[tuple[str, ...]] = ("__pycache__", ".pytest_cache", ".ruff_cache", ".mypy_cache")


class _Digest(Protocol):
    def update(self, data: bytes, /) -> None: ...


def _hash_tree(digest: _Digest, root: Path, *, label: str) -> None:
    if not root.exists():
        digest.update(f"absent:{label}\n".encode())
        return
    files = (
        [root]
        if root.is_file()
        else scan_directory(root, recursive=True, select=DirectoryEntryKind.FILES, prune_directories=_PRUNED)
    )
    for path in files:
        relative = path.relative_to(root).as_posix() if path != root else path.name
        digest.update(f"{label}/{relative}\n".encode())
        with path.open("rb") as handle:
            digest.update(hashlib.file_digest(handle, "sha256").digest())


def _hash_directives(digest: _Digest, docs_root: Path) -> None:
    """Hash only the directives each page enrolls; page prose does not change a verdict."""
    pages = scan_directory(
        docs_root,
        pattern="*.md",
        recursive=True,
        select=DirectoryEntryKind.FILES,
        prune_directories=("_build", "locales", *_PRUNED),
    )
    for page in pages:
        directives = _DIRECTIVE_RE.findall(page.read_text(encoding="utf-8"))
        if directives:
            digest.update(f"page/{page.relative_to(docs_root).as_posix()}\n".encode())
            digest.update("\n".join(directives).encode())


def verdict_key(
    *,
    docs_root: Path,
    goldens_root: Path | None,
    authority_generation: str,
    repo_root: Path = REPO_ROOT,
) -> str:
    """Return the content key of everything the gate's verdict depends on."""
    digest = hashlib.sha256()
    digest.update(f"python:{sys.version}\nplatform:{platform.system()}\nauthority:{authority_generation}\n".encode())
    _hash_tree(digest, repo_root / "src" / "cadrumo", label="src")
    _hash_tree(digest, repo_root / "dev" / "docs" / "sequences", label="engine")
    for module in ("sequence_build_gate.py", "build.py"):
        _hash_tree(digest, repo_root / "dev" / "docs" / module, label=f"engine/{module}")
    _hash_tree(digest, repo_root / "uv.lock", label="lock")
    _hash_tree(digest, docs_root / "_sequences", label="sequences")
    if goldens_root is not None:
        _hash_tree(digest, goldens_root, label="goldens")
    _hash_directives(digest, docs_root)
    return digest.hexdigest()


def _record_path(key: str) -> Path:
    return dev_cache_dir(_CACHE_NAME) / f"{key}.json"


def reused_verdict(key: str) -> str | None:
    """Return a description of the recorded clean verdict for ``key``, or ``None`` to run the gate."""
    if os.environ.get(FORCE_ENV):
        return None
    record = _record_path(key)
    try:
        document = json.loads(record.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if document.get("verdict") != "clean" or document.get("key") != key:
        return None
    return f"reused clean verdict {key[:12]} recorded {document.get('recorded_at')}"


def record_clean_verdict(key: str) -> None:
    """Record that the gate passed for ``key``; a failure to record costs only a future re-run."""
    record = _record_path(key)
    try:
        record.parent.mkdir(parents=True, exist_ok=True)
        record.write_text(
            json.dumps({"key": key, "verdict": "clean", "recorded_at": datetime.now(UTC).isoformat()}),
            encoding="utf-8",
        )
    except OSError:
        return
