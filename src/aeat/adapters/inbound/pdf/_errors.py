"""Root exception for every PDF-import-side error.

The canonical class lives in :mod:`aeat.domain.justificante._errors`
because it is the project-wide root for every PDF-import failure
(declaración / borrador / justificante). This module simply re-
exports it so adapter code can use the local-package import path
without introducing a duplicate class identity that would conflict
with the error-code registry.
"""

from __future__ import annotations

from ....domain.justificante._errors import PdfModeloImportError

__all__ = ["PdfModeloImportError"]
