"""Regenerate ``docs/api/`` Sphinx automodule stubs for the ``aeat`` package.

Each Python module in the ``aeat`` source tree is documented exactly once:

- **Package stubs** (modules whose path ends in ``__init__.py``) emit only
  the package docstring via ``.. automodule:: <pkg>`` without ``:members:``,
  plus ``.. toctree::`` blocks for direct sub-packages and direct
  sub-modules.  Members are documented by their defining module stubs, not
  pulled up into the package page.
- **Module stubs** (every non-``__init__.py`` file, including private
  ``_*`` files) emit ``.. automodule:: <mod>`` with ``:members:`` and
  ``:show-inheritance:``.  This is the single authoritative documentation
  point for every symbol.

The two-level structure ensures that ``__all__``-driven re-exports in
package ``__init__`` files never cause Sphinx to document the same class
or function twice, eliminating ``duplicate object description`` warnings
under the nitpicky (``-n``) build.

Excluded from generation:

- ``aeat.tests`` and any path beneath it.
- ``aeat._data`` and any path beneath it.
- Files matching ``test_*.py``, ``_test_*.py``, or ``conftest.py``.

Usage::

    uv run --no-sync python scripts/gen_api_stubs.py [--dry-run]

The script is idempotent: running it again regenerates the same files.
The caller is responsible for committing the result; this script makes no
git operations.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Final

# ── Encoding constant ─────────────────────────────────────────────────────────

_UTF_8: Final[str] = "utf-8"

# ── Path constants ────────────────────────────────────────────────────────────

_REPO_ROOT = Path(__file__).resolve().parents[1]
_SRC_AEAT = _REPO_ROOT / "src" / "aeat"
_DOCS_API = _REPO_ROOT / "docs" / "api"

_PACKAGE_ROOT = "aeat"

# Module segments that exclude an entire subtree.
_EXCLUDED_PACKAGES: frozenset[str] = frozenset({"tests", "_data"})

# File-name patterns that exclude individual modules (even inside included pkgs).
_EXCLUDED_FILENAMES: frozenset[str] = frozenset({"conftest.py"})


# ── Discovery ─────────────────────────────────────────────────────────────────


def _is_excluded_path(path: Path) -> bool:
    """Return True when *path* falls inside an excluded subtree or filename.

    Args:
        path: An absolute ``Path`` under ``_SRC_AEAT``.

    Returns:
        True when the path should be skipped.
    """
    relative = path.relative_to(_SRC_AEAT)
    parts = relative.parts

    # Exclude files whose name matches a test-file pattern.
    filename = path.name
    if filename.startswith("test_") or filename.startswith("_test_"):
        return True
    if filename in _EXCLUDED_FILENAMES:
        return True

    # Exclude any path whose first segment is an excluded package name.
    return bool(parts and parts[0] in _EXCLUDED_PACKAGES)


def _discover_modules(src_root: Path) -> list[tuple[str, bool]]:
    """Walk *src_root* and collect (dotted_module_name, is_package) pairs.

    Args:
        src_root: The ``src/aeat`` directory.

    Returns:
        Sorted list of ``(dotted_name, is_package)`` tuples.  ``is_package``
        is True for ``__init__.py`` files.
    """
    results: list[tuple[str, bool]] = []

    for py_file in sorted(src_root.rglob("*.py")):
        if _is_excluded_path(py_file):
            continue

        relative = py_file.relative_to(src_root.parent)
        # relative is like ``aeat/adapters/inbound/__init__.py``
        parts = list(relative.parts)

        if parts[-1] == "__init__.py":
            # Package: dotted name is everything except ``__init__.py``.
            dotted = ".".join(parts[:-1])
            results.append((dotted, True))
        else:
            # Module: strip ``.py`` suffix.
            parts[-1] = parts[-1][: -len(".py")]
            dotted = ".".join(parts)
            results.append((dotted, False))

    return results


# ── Stub content builders ─────────────────────────────────────────────────────


def _package_children(
    pkg_name: str,
    all_modules: list[tuple[str, bool]],
) -> tuple[list[str], list[str]]:
    """Return direct sub-packages and direct sub-modules of *pkg_name*.

    A direct child has exactly one more dotted segment than *pkg_name* and
    is *not* a package itself (for sub-modules) or *is* a package (for
    sub-packages).

    Args:
        pkg_name: Dotted name of the package whose children to find.
        all_modules: Full discovery output from :func:`_discover_modules`.

    Returns:
        A ``(sub_packages, sub_modules)`` pair, each sorted.
    """
    prefix = pkg_name + "."
    prefix_depth = pkg_name.count(".") + 1

    sub_packages: list[str] = []
    sub_modules: list[str] = []

    for name, is_pkg in all_modules:
        if not name.startswith(prefix):
            continue
        depth = name.count(".")
        if depth != prefix_depth:
            # Not a direct child — grandchild or deeper.
            continue
        if is_pkg:
            sub_packages.append(name)
        else:
            sub_modules.append(name)

    return sorted(sub_packages), sorted(sub_modules)


def _heading(text: str) -> str:
    """Build an RST section heading with ``=`` underline.

    Args:
        text: The heading text.

    Returns:
        A two-line string: the text followed by an equal-length ``=`` underline.
    """
    return f"{text}\n{'=' * len(text)}"


def _toctree_block(entries: list[str], label: str) -> str:
    """Build an RST ``toctree`` block.

    Args:
        entries: List of toctree entry strings (relative RST references).
        label: Section label placed above the toctree.

    Returns:
        An RST string containing the labelled section and toctree directive.
    """
    lines: list[str] = [
        "",
        label,
        "-" * len(label),
        "",
        ".. toctree::",
        "   :maxdepth: 4",
        "",
    ]
    for entry in entries:
        lines.append(f"   {entry}")
    return "\n".join(lines)


def _package_stub(
    pkg_name: str,
    sub_packages: list[str],
    sub_modules: list[str],
) -> str:
    """Generate RST content for a package stub.

    The package page documents the package docstring only (no ``:members:``
    so that re-exported symbols are not pulled in here).  Sub-packages and
    sub-modules are listed in separate ``toctree`` blocks.

    Args:
        pkg_name: Dotted name of the package.
        sub_packages: Direct child package names.
        sub_modules: Direct child module names.

    Returns:
        Complete RST source for the stub file.
    """
    title = f"{pkg_name} package"
    lines: list[str] = [
        _heading(title),
        "",
        f".. automodule:: {pkg_name}",
        # Override the global ``autodoc_default_options`` which enables ``:members:``
        # project-wide.  Package stubs show only the package docstring; every
        # symbol is documented exactly once in the stub for its defining module.
        "   :no-members:",
        "",
    ]

    if sub_packages:
        lines.append(
            _toctree_block(
                sub_packages,
                "Subpackages",
            )
        )

    if sub_modules:
        lines.append(
            _toctree_block(
                sub_modules,
                "Submodules",
            )
        )

    lines.append("")
    return "\n".join(lines)


def _module_stub(mod_name: str) -> str:
    """Generate RST content for a leaf-module stub.

    The module page documents every public member at the source where it is
    defined, preventing any re-export duplication.

    Args:
        mod_name: Dotted name of the module.

    Returns:
        Complete RST source for the stub file.
    """
    title = f"{mod_name} module"
    lines: list[str] = [
        _heading(title),
        "",
        f".. automodule:: {mod_name}",
        "   :members:",
        "   :show-inheritance:",
        "",
    ]
    return "\n".join(lines)


# ── Root index stub ───────────────────────────────────────────────────────────


def _root_package_stub(
    pkg_name: str,
    sub_packages: list[str],
    sub_modules: list[str],
) -> str:
    """Generate the root ``aeat`` package stub.

    Identical to :func:`_package_stub` but exists as a named entry so
    callers can distinguish it for the ``modules.rst`` cross-reference check.

    Args:
        pkg_name: The root package name (``"aeat"``).
        sub_packages: Direct child packages.
        sub_modules: Direct child modules.

    Returns:
        Complete RST for ``docs/api/aeat.rst``.
    """
    return _package_stub(pkg_name, sub_packages, sub_modules)


def _modules_rst() -> str:
    """Generate ``docs/api/modules.rst``.

    This stub exists so that ``docs/index.rst`` can reference ``api/aeat``
    via the standard toctree entry ``api/aeat``.  It points at the root
    ``aeat`` stub.

    Returns:
        Complete RST for ``docs/api/modules.rst``.
    """
    return "aeat\n====\n\n.. toctree::\n   :maxdepth: 4\n\n   aeat\n"


# ── File I/O ──────────────────────────────────────────────────────────────────


def _stub_filename(dotted_name: str) -> str:
    """Convert a dotted module name to its ``.rst`` filename stem.

    Args:
        dotted_name: Dotted Python module name.

    Returns:
        The corresponding ``docs/api/`` filename (e.g. ``aeat.core.rst``).
    """
    return f"{dotted_name}.rst"


def _write_stub(api_dir: Path, filename: str, content: str, dry_run: bool) -> None:
    """Write a single stub file to *api_dir*.

    Args:
        api_dir: Target ``docs/api/`` directory.
        filename: Destination filename (not a full path).
        content: RST content to write.
        dry_run: When True, print what would be written without touching disk.
    """
    dest = api_dir / filename
    if dry_run:
        print(f"[dry-run] would write: {dest}")
        return
    dest.write_text(content, encoding=_UTF_8)


# ── Cleanup of stale stubs ────────────────────────────────────────────────────


def _remove_stale_stubs(
    api_dir: Path,
    expected_filenames: set[str],
    dry_run: bool,
) -> int:
    """Remove ``.rst`` files that are no longer generated.

    Args:
        api_dir: The ``docs/api/`` directory.
        expected_filenames: Set of filenames that the generator produces.
        dry_run: When True, print what would be removed without touching disk.

    Returns:
        Count of files removed (or that would be removed in dry-run mode).
    """
    count = 0
    for existing in sorted(api_dir.glob("*.rst")):
        if existing.name not in expected_filenames:
            if dry_run:
                print(f"[dry-run] would remove stale: {existing}")
            else:
                existing.unlink()
                print(f"Removed stale stub: {existing.name}")
            count += 1
    return count


# ── Main ──────────────────────────────────────────────────────────────────────


def main(argv: list[str] | None = None) -> int:
    """Entry point for the stub generator.

    Args:
        argv: Argument list; defaults to ``sys.argv[1:]``.

    Returns:
        Exit code (0 on success).
    """
    parser = argparse.ArgumentParser(
        description=__doc__.splitlines()[0],
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print what would be written without modifying the filesystem.",
    )
    args = parser.parse_args(argv)
    dry_run: bool = args.dry_run

    # Ensure the output directory exists.
    if not dry_run:
        _DOCS_API.mkdir(parents=True, exist_ok=True)

    # Discover all in-scope modules.
    all_modules = _discover_modules(_SRC_AEAT)

    expected_filenames: set[str] = set()
    written = 0

    # Generate a stub for every discovered module.
    for name, is_pkg in all_modules:
        if is_pkg:
            sub_pkgs, sub_mods = _package_children(name, all_modules)
            content = _package_stub(name, sub_pkgs, sub_mods)
        else:
            content = _module_stub(name)

        filename = _stub_filename(name)
        expected_filenames.add(filename)
        _write_stub(_DOCS_API, filename, content, dry_run)
        written += 1

    # Always emit modules.rst.
    expected_filenames.add("modules.rst")
    _write_stub(_DOCS_API, "modules.rst", _modules_rst(), dry_run)

    # Remove any stale stubs left over from the previous hand-authored set.
    removed = _remove_stale_stubs(_DOCS_API, expected_filenames, dry_run)

    print(
        f"{'[dry-run] ' if dry_run else ''}"
        f"Generated {written} stubs, removed {removed} stale stubs."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
