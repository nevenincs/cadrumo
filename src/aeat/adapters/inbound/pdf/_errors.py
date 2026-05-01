"""Root exception for every PDF-import-side error.

Every PDF-class module (:mod:`aeat.domain.justificante`, :mod:`aeat.adapters.inbound.declaracion`,
:mod:`aeat.adapters.inbound.borrador`) defines its own ``*Error``
subclass that inherits :class:`PdfFilingImportError`, which itself inherits
the project-wide :class:`aeat.core.errors.AeatError`. Callers wanting to catch
every PDF-import error regardless of source use :class:`PdfFilingImportError`.
"""

from __future__ import annotations

from ....domain.justificante._errors import PdfFilingImportError
