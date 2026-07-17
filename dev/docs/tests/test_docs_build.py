"""Documentation build conformance gate.

Runs a real nitpicky, warnings-as-errors Sphinx build and asserts it
succeeds. Every unresolved cross-reference or malformed directive fails the
build. The test carries the active ``unit`` and ``hex_core`` markers; it builds into a ``tmp_path`` and
sets ``AEAT_DOCS_OFFLINE`` so intersphinx inventories are not fetched.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.hex_core, pytest.mark.docs]

_REPO_ROOT = Path(__file__).resolve().parents[3]
_DOCS = _REPO_ROOT / "docs"
_DOCS_BUILD = _DOCS / "_build"
_CANONICAL_BUILD_ROOT = "html"
_DOCS_BUILD_LITERAL_RE = re.compile(r"docs[/\\]_build[/\\]([A-Za-z0-9_.-]+)")
_PATH_BUILD_ROOT_RE = re.compile(r"[\"']_build[\"']\s*/\s*[\"']([^\"']+)[\"']")
_BUILD_ROOT_SCAN_PREFIXES = ("src/", "dev/", ".github/")
_BUILD_ROOT_SCAN_FILES = {"justfile", "pyproject.toml", "docs/conf.py"}


def _docs_build_entries() -> set[str]:
    """Return entry names currently present directly under ``docs/_build``."""
    if not _DOCS_BUILD.exists():
        return set()
    return {path.name for path in _DOCS_BUILD.iterdir()}


def _docs_source_paths() -> set[tuple[str, str]]:
    """Return the live docs source path set, excluding build output."""
    paths: set[tuple[str, str]] = set()
    for path in _DOCS.rglob("*"):
        relative = path.relative_to(_DOCS)
        if relative.parts and relative.parts[0] == "_build":
            continue
        kind = "dir" if path.is_dir() else "file"
        paths.add((relative.as_posix(), kind))
    return paths


def _generated_docs_snapshot() -> set[tuple[str, str, int, int]]:
    """Return metadata for generated docs sources that validation must not touch."""
    snapshot: set[tuple[str, str, int, int]] = set()
    for root_name in ("api", "cli"):
        root = _DOCS / root_name
        if not root.exists():
            continue
        for path in root.rglob("*"):
            relative = path.relative_to(_DOCS)
            stat = path.stat()
            kind = "dir" if path.is_dir() else "file"
            size = stat.st_size if path.is_file() else 0
            snapshot.add((relative.as_posix(), kind, size, stat.st_mtime_ns))
    return snapshot


def test_docs_build_directory_contains_only_canonical_html() -> None:
    """The repository docs build directory must not contain preview/test output."""
    entries = _docs_build_entries()
    extra = sorted(entries - {_CANONICAL_BUILD_ROOT})
    assert not extra, (
        "docs/_build must contain only the actual canonical HTML build root. "
        "Tests and changed-page validation must write to tmp_path or an OS temp "
        f"directory, not docs/_build. Extra entries: {extra}"
    )


def test_docs_build_cleanup_removes_noncanonical_entries(tmp_path: Path) -> None:
    """Canonical docs builds clear stale preview files from their build root."""
    from dev.docs.build import remove_noncanonical_build_entries

    docs_root = tmp_path / "docs"
    build_root = docs_root / "_build"
    html_root = build_root / _CANONICAL_BUILD_ROOT
    preview_dir = build_root / "index-preview"
    preview_file = build_root / "md-preview.html"
    html_root.mkdir(parents=True)
    preview_dir.mkdir()
    preview_file.write_text("<title>preview</title>\n", encoding="utf-8")

    remove_noncanonical_build_entries(docs_root)

    assert sorted(path.name for path in build_root.iterdir()) == [_CANONICAL_BUILD_ROOT]
    assert html_root.is_dir()


@pytest.mark.parametrize(
    "changed_path",
    [
        "dev/docs/apidocs/manager.py",
        "dev/docs/cli_reference.py",
    ],
)
def test_changed_docs_validation_does_not_pollute_repository_docs(changed_path: str) -> None:
    """Changed-page validation writes generated sources and output outside live docs."""
    before = _docs_build_entries()
    paths_before = _docs_source_paths()
    generated_before = _generated_docs_snapshot()
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "dev.docs.build",
            changed_path,
        ],
        cwd=_REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    after = _docs_build_entries()
    paths_after = _docs_source_paths()
    generated_after = _generated_docs_snapshot()
    assert result.returncode == 0, (
        "changed-doc validation failed:\n" + (result.stdout or "")[-3000:] + (result.stderr or "")[-3000:]
    )
    assert after == before, (
        "changed-doc validation must not add or remove docs/_build entries. "
        f"Before: {sorted(before)}; after: {sorted(after)}"
    )
    assert paths_after == paths_before, (
        "changed-doc validation must not add or remove live docs source paths. "
        "Validation scratch files belong in the temporary docs source tree."
    )
    assert generated_after == generated_before, (
        "changed-doc validation must not mutate live generated docs sources. "
        "Generated API/CLI pages for validation belong in the temporary docs source tree."
    )


@pytest.mark.parametrize("generated_page", ["docs/api/aeat.rst", "docs/cli/index.rst"])
def test_single_page_rejects_generated_documentation_sources(generated_page: str) -> None:
    """Single-page canonical builds must not regenerate API or CLI source trees."""
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "dev.docs.build",
            "--single-page",
            generated_page,
        ],
        cwd=_REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode != 0
    assert "--single-page does not support generated API/CLI pages" in result.stderr


def test_tracked_sources_do_not_name_noncanonical_docs_build_roots() -> None:
    """Tracked code must not introduce preview/test output roots under ``docs/_build``."""
    git = shutil.which("git")
    assert git is not None, "git executable is required for docs build hygiene"
    result = subprocess.run(
        [git, "ls-files"],
        cwd=_REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, "git ls-files is required for docs build hygiene"

    violations: list[str] = []
    for raw_path in result.stdout.splitlines():
        normalised = raw_path.replace("\\", "/")
        if not (normalised in _BUILD_ROOT_SCAN_FILES or normalised.startswith(_BUILD_ROOT_SCAN_PREFIXES)):
            continue
        path = _REPO_ROOT / raw_path
        if not path.is_file() or "docs/_build" in normalised:
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        roots = [*_DOCS_BUILD_LITERAL_RE.findall(text), *_PATH_BUILD_ROOT_RE.findall(text)]
        for root in roots:
            if root != _CANONICAL_BUILD_ROOT:
                violations.append(f"{raw_path}: docs/_build/{root}")

    assert not violations, (
        "Only docs/_build/html is an allowed repository-local docs build root. "
        "Use tmp_path or an OS temporary directory for validation/previews:\n  " + "\n  ".join(sorted(set(violations)))
    )


def test_sphinx_nitpicky_build_is_clean(tmp_path: Path) -> None:
    """The nitpicky, warnings-as-errors build must succeed.

    Uses the ``dummy`` builder, not ``html``: the gate only asserts that the
    full parse and cross-reference resolution (where ``-n`` nitpicky warnings
    fire) raise no warnings under ``-W``; it does not need rendered HTML, so
    rendered-page emission is skipped. ``-j auto`` parallelises the autodoc read across
    every core, since the cost is dominated by importing and introspecting the
    several-hundred ``automodule`` stubs. Together these cut the build from tens
    of minutes to a fraction without weakening the check.

    Args:
        tmp_path: Pytest-provided isolated output directory.
    """
    docs_source = tmp_path / "docs-source"
    shutil.copytree(_DOCS, docs_source, ignore=shutil.ignore_patterns("_build", "cli"))
    env = {**os.environ, "AEAT_DOCS_OFFLINE": "1", "AEAT_DOCS_PROJECT_ROOT": str(_REPO_ROOT)}
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "sphinx",
            "-b",
            "dummy",
            "-n",
            "-W",
            "-j",
            "auto",
            str(docs_source),
            str(tmp_path / "out"),
        ],
        cwd=_REPO_ROOT,
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )
    assert result.returncode == 0, (
        "nitpicky sphinx build reported warnings or errors:\n"
        + (result.stdout or "")[-6000:]
        + (result.stderr or "")[-6000:]
    )
