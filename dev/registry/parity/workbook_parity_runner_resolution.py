"""Resolve supported local workbook runner executables."""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import TYPE_CHECKING

from cadrumo.domain.calculations.registry.errors import RegistryValidationError

if TYPE_CHECKING:
    # Annotation-only: ``from __future__ import annotations`` above makes every
    # annotation a string, so these need not exist at runtime. openpyxl is one of
    # the heaviest third-party imports in the tree and this module is imported
    # eagerly by the registry facade, so the symbols that ARE needed at runtime
    # (``load_workbook``, ``Tokenizer``, and the ``TokenizerError`` /
    # ``InvalidFileException`` handler types) are imported inside the functions
    # that use them -- a taxpayer calculation must not load a spreadsheet engine.
    pass


def _resolve_libreoffice_runner(executable: str | None) -> Path:
    """Locate a LibreOffice executable, raising explicitly when none is available."""
    if executable is None:
        found = shutil.which("soffice") or shutil.which("libreoffice")
        if not found:
            raise RegistryValidationError(
                "LibreOffice or soffice executable is not available on PATH. "
                "Install LibreOffice and expose its executable on PATH.",
            )
        return Path(found).resolve()
    candidate = Path(executable).resolve()
    if not candidate.is_file():
        raise RegistryValidationError(f"LibreOffice executable does not exist: {executable}")
    if candidate.name.lower() not in {"soffice", "soffice.exe", "libreoffice", "libreoffice.exe"}:
        raise RegistryValidationError(f"unsupported LibreOffice executable name: {candidate.name}")
    return candidate
