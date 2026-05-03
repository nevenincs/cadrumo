"""Root exception for every PDF-import-side error.

Every PDF-class module (:mod:`aeat.domain.justificante`, :mod:`aeat.adapters.inbound.declaracion`,
:mod:`aeat.adapters.inbound.borrador`) defines its own ``*Error``
subclass that inherits :class:`PdfFilingImportError`, which itself inherits
the project-wide :class:`aeat.core.errors.AeatError`. Callers wanting to catch
every PDF-import error regardless of source use :class:`PdfFilingImportError`.
"""

from __future__ import annotations

from ....core.errors import AeatError


class PdfFilingImportError(AeatError):
    """Root error for every PDF-import-side failure.

    Every concrete PDF-import error class (declaracion / borrador /
    justificante) inherits this so callers that only need to catch
    "any PDF parsing problem" can do so by referencing this class
    rather than the per-source subclasses.
    """
