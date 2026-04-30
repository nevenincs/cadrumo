"""Root exception for every PDF-import-side error.

Every PDF-class module (:mod:`aeat.justificante`, :mod:`aeat.declaracion`,
:mod:`aeat.borrador`, :mod:`aeat.predeclaracion`) defines its own ``*Error``
subclass that inherits :class:`PdfFilingImportError`, which itself inherits
the project-wide :class:`aeat.errors.AeatError`. Callers wanting to catch
every PDF-import error regardless of source use :class:`PdfFilingImportError`.
"""

from __future__ import annotations

from ....core.errors import AeatError


class PdfFilingImportError(AeatError):
    """Base class for every PDF-import parsing error."""
