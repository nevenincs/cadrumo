"""Shared scan helpers for the import-boundary gates.

These were previously private helpers inside the import-hygiene gate module,
which was retired along with its hand-maintained baseline and test-debt
ledgers. The scan itself carries no exemption list: it walks the shipped
package and returns what is actually there, so the surviving gates that assert
hard zeros keep a single cached walk to share.
"""

from __future__ import annotations

from functools import cache
from pathlib import Path

from cadrumo.core.directory_scan import scan_directory

from ..quality.import_hygiene_scan import PKG_ROOT, ImportSite, walk_module_imports


@cache
def _scanned_py_files() -> tuple[Path, ...]:
    """Walk the shipped package once per process.

    The ``walk_module_imports`` pass carries no memo and measures ~18s over the
    shipped tree, so it is paid once here and shared by every consuming gate.
    """
    return tuple(
        sorted(p for p in scan_directory(PKG_ROOT, pattern="*.py", recursive=True) if "__pycache__" not in p.parts)
    )


@cache
def _scanned_import_sites() -> tuple[ImportSite, ...]:
    """Collect every import site in the shipped package once per process."""
    return tuple(site for path in _scanned_py_files() for site in walk_module_imports(path))


def _package_py_files() -> list[Path]:
    """Return the shipped module list, rebuilt per caller from the cached walk.

    A list rather than the cached tuple, so each gate owns its own sequence and
    passes the scanners exactly the type they received before.
    """
    return list(_scanned_py_files())


def _package_import_sites() -> list[ImportSite]:
    """Return every import site, rebuilt per caller from the cached pass."""
    return list(_scanned_import_sites())


def _plant_module(root: Path, dotted_rel: str, body: str) -> Path:
    """Write a synthetic module at ``dotted_rel`` under ``root`` and return its path."""
    path = root / dotted_rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")
    return path
