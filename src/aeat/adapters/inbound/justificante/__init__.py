"""Inbound parser adapter for AEAT justificante PDFs.

Parses the receipt PDF the AEAT issues after a filing (the justificante)
into a strict domain record, so the reconcile workflow can compare a filed
return against its official receipt. The defining domain records live in
:mod:`aeat.domain.justificante`.

Major declaration:

* :func:`parse_justificante` — parse a justificante PDF into its typed
  domain record.
"""

from __future__ import annotations

from ._parser import parse_justificante

__all__ = [
    "parse_justificante",
]
