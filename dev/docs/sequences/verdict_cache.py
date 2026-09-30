"""Reuse a clean cli-sequence gate verdict when nothing it depends on has changed.

The gate executes every documented CLI sequence against the real CLI and
compares the transcripts with their committed goldens. Its verdict is a pure
function of the product source (the CLI, its registry data and the golden mask
set), the gate engine and every ``dev`` module it imports, the sequence
contracts, goldens, seeds and fixtures, the directives the pages enroll, the
published registry authority, the locked dependencies and the interpreter. The
key hashes all of them, enumerated from the filesystem and from the engine's
static import graph, so any change to any input is a cache miss and a re-run.
The registry tooling is the one deliberate omission: it reaches the verdict
only through the published authority, whose generation the key carries.

Only a clean verdict is stored. A divergence is never cached, so a cache can
cost a re-run but can never turn a failing gate green; a hit always says which
recorded verdict it reused.
"""

from __future__ import annotations

import ast
import hashlib
import json
import os
import platform
import re
import sys
from collections.abc import Callable, Iterator
from datetime import UTC, datetime
from pathlib import Path
from typing import Final, Protocol

from cadrumo.core.directory_scan import DirectoryEntryKind, scan_directory
from dev._paths import REPO_ROOT
from dev.cache_root import dev_cache_dir

from .authority_currency import require_current_authority

#: Set to bypass the cache and always execute the gate.
FORCE_ENV: Final[str] = "CADRUMO_DOCS_FORCE_SEQUENCE_CHECK"
_CACHE_NAME: Final[str] = "docs-sequence-verdicts"
_DIRECTIVE_RE: Final[re.Pattern[str]] = re.compile(r"^```\{cli-sequence\}.*?^```", re.MULTILINE | re.DOTALL)
_PRUNED: Final[tuple[str, ...]] = ("__pycache__", ".pytest_cache", ".ruff_cache", ".mypy_cache")
#: The engine's entry points; every ``dev`` module they import, transitively, is a verdict input.
ENGINE_ROOTS: Final[tuple[str, ...]] = ("dev/docs/sequences", "dev/docs/sequence_build_gate.py", "dev/docs/build.py")
#: Registry tooling reaches the verdict only through the published authority,
#: whose generation the key already carries. Following its imports would re-run
#: the gate for every registry-tool edit without adding an input.
_AUTHORITY_TOOLING: Final[str] = "dev/registry/"


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


def _is_type_checking_guard(node: ast.If) -> bool:
    test = node.test
    return (isinstance(test, ast.Name) and test.id == "TYPE_CHECKING") or (
        isinstance(test, ast.Attribute) and test.attr == "TYPE_CHECKING"
    )


def _imported_modules(tree: ast.Module, package: str) -> Iterator[str]:
    """Yield every dotted name a module may import at runtime, including lazy imports.

    Relative imports resolve against ``package``. ``from a import b`` yields both
    ``a`` and ``a.b`` because ``b`` may be a submodule; a name that is not a module
    simply resolves to no file.
    """
    pending: list[ast.AST] = list(tree.body)
    while pending:
        node = pending.pop()
        if isinstance(node, ast.If) and _is_type_checking_guard(node):
            pending.extend(node.orelse)
            continue
        if isinstance(node, ast.Import):
            yield from (alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                parts = package.split(".")
                base = ".".join(parts[: len(parts) - node.level + 1])
                module = f"{base}.{node.module}" if node.module else base
            else:
                module = node.module or ""
            yield module
            yield from (f"{module}.{alias.name}" for alias in node.names)
        pending.extend(ast.iter_child_nodes(node))


def _dev_module_files(repo_root: Path, module: str) -> Iterator[Path]:
    """Yield the files importing ``module`` executes: each package ``__init__`` and the module itself."""
    parts = module.split(".")
    if parts[0] != "dev":
        return
    for end in range(1, len(parts) + 1):
        base = repo_root.joinpath(*parts[:end])
        for candidate in (base / "__init__.py", base.with_suffix(".py")):
            if candidate.is_file():
                yield candidate


def engine_import_closure(repo_root: Path = REPO_ROOT) -> tuple[str, ...]:
    """Return the engine's files and every ``dev`` module they import, transitively.

    The graph is read statically, so the result is the same in every process that
    computes a key. Imports guarded by ``TYPE_CHECKING`` never run and are skipped;
    registry tooling is excluded for the reason given on ``_AUTHORITY_TOOLING``.

    Returns:
        Repository-relative POSIX paths, sorted.
    """
    pending: list[Path] = []
    for root in ENGINE_ROOTS:
        path = repo_root / root
        if path.is_file():
            pending.append(path)
        elif path.is_dir():
            pending.extend(
                scan_directory(
                    path,
                    pattern="*.py",
                    recursive=True,
                    select=DirectoryEntryKind.FILES,
                    prune_directories=("tests", *_PRUNED),
                )
            )
    seen: set[Path] = set()
    while pending:
        path = pending.pop()
        if path in seen:
            continue
        seen.add(path)
        package = ".".join(path.relative_to(repo_root).parent.parts)
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for module in _imported_modules(tree, package):
            for imported in _dev_module_files(repo_root, module):
                if not imported.relative_to(repo_root).as_posix().startswith(_AUTHORITY_TOOLING):
                    pending.append(imported)
    return tuple(sorted(path.relative_to(repo_root).as_posix() for path in seen))


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
    for relative in engine_import_closure(repo_root):
        _hash_tree(digest, repo_root / relative, label=f"engine-import/{relative}")
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


def published_verdict_key(*, docs_root: Path, goldens_root: Path | None) -> str:
    """Return the verdict key under the published authority the runner will read.

    A stale authority is refused before its generation can key anything, so a
    clean verdict recorded under it can never be reused.

    Raises:
        SequenceEngineError: When the published authority is not current.
    """
    from cadrumo.domain.calculations.registry.authority import bundled_indexed_authority

    require_current_authority()
    with bundled_indexed_authority().operation() as operation:
        generation = str(operation.generation)
    return verdict_key(docs_root=docs_root, goldens_root=goldens_root, authority_generation=generation)


def check_reusing_verdict(key: str, check: Callable[[], tuple[str, ...]]) -> tuple[tuple[str, ...], str | None]:
    """Run ``check`` unless a clean verdict is recorded for ``key``, recording it when clean.

    The docs build and the merge gate both go through this one flow, so neither
    can reuse or record a verdict on terms the other would not.

    Returns:
        The problems ``check`` reported, and the description of the recorded
        verdict when one stood in for execution (``None`` when ``check`` ran).
    """
    reused = reused_verdict(key)
    if reused is not None:
        return (), reused
    problems = check()
    if not problems:
        record_clean_verdict(key)
    return problems, None
