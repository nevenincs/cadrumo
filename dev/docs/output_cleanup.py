"""Remove obsolete documentation build outputs."""

from __future__ import annotations

import shutil
from pathlib import Path

from cadrumo.core.directory_scan import scan_directory
from cadrumo.core.external_constants import OutputLanguage

#: Builder-owned pages with no corresponding source document.
_ORPHAN_SPECIAL_PAGES = {"genindex.html", "search.html", "404.html", "py-modindex.html"}

#: Asset and infrastructure directories that carry no docname-addressed pages.
_ORPHAN_SKIP_DIRS = {"_static", "_sources", "_images", "_downloads", "_sphinx_design_static", "pagefind"}

#: Per-language site roots living beside the English root inside the same HTML
#: tree. Their pages are docname-addressed against the SAME ``docs/`` sources,
#: one directory level down, so the sweep below would resolve ``es/index.html``
#: to a ``docs/es/index.md`` that never existed and delete every page of every
#: localized root. Derived from :class:`OutputLanguage` rather than imported
#: from the module that names the deploy root set, because that module imports
#: this one.
_ORPHAN_SKIP_SITE_ROOTS = frozenset(member.value for member in OutputLanguage)


def remove_orphan_pages(docs_root: Path, html_root: Path, repo_root: Path) -> int:
    """Delete built pages whose source document no longer exists.

    Furo bakes the theme's variables and templates into every page at build
    time, so a page whose source was removed or renamed keeps rendering its
    build-era design indefinitely and leaks stale results into the search
    index (the docs-brand audit found 2208 such orphans rendering a retired
    theme). Every docname maps to a ``.md``/``.rst`` source under ``docs/`` —
    including the generated ``api/``, ``cli/``, and ``_generated/`` sources,
    which are written to disk before Sphinx reads the tree — and ``_modules``
    viewcode pages map back to ``src/`` modules.

    A per-language site root nested in the same tree is exempt: its pages carry
    the same docnames one directory down, so resolving them against ``docs/``
    finds nothing and an apex build would empty every localized root beside it.

    Returns:
        The number of orphaned pages removed.
    """
    if not html_root.exists():
        return 0
    removed = 0
    for page in scan_directory(html_root, pattern="*.html", recursive=True):
        removed += int(_remove_orphan_page(page, html_root, docs_root, repo_root))
    if removed:
        print(f"Removed {removed} orphaned page(s) whose source no longer exists.", flush=True)
    return removed


def remove_noncanonical_build_entries(build_root: Path) -> None:
    """Remove stale entries beside the canonical HTML and doctree trees."""
    if not build_root.exists():
        return
    allowed = {(build_root / "html").resolve(), (build_root / "doctrees").resolve()}
    for entry in scan_directory(build_root):
        resolved = entry.resolve()
        if resolved in allowed:
            continue
        if build_root.resolve() not in resolved.parents:
            raise SystemExit(f"Refusing to remove docs build entry outside the configured build root: {entry}")
        if entry.is_dir():
            shutil.rmtree(entry)
        else:
            entry.unlink()


def _remove_orphan_page(page: Path, html_root: Path, docs_root: Path, repo_root: Path) -> bool:
    rel = page.relative_to(html_root)
    if rel.as_posix() in _ORPHAN_SPECIAL_PAGES or rel.parts[0] in _ORPHAN_SKIP_DIRS:
        return False
    if rel.parts[0] in _ORPHAN_SKIP_SITE_ROOTS and len(rel.parts) > 1:
        return False
    docname = rel.with_suffix("")
    if rel.parts[0] == "_modules":
        if rel.as_posix() == "_modules/index.html":
            return False
        module_path = Path(*docname.parts[1:])
        candidates = [repo_root / "src" / Path(f"{module_path}.py")]
    else:
        candidates = [docs_root / Path(f"{docname}{suffix}") for suffix in (".md", ".rst")]
    if any(candidate.is_file() for candidate in candidates):
        return False
    page.unlink()
    return True
