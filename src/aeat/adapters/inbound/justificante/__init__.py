"""Inbound parser adapter for AEAT justificante PDFs.

Parses the receipt PDF the AEAT issues after a filing (the justificante)
into a strict domain record, so the reconcile workflow can compare a filed
return against its official receipt. The defining domain records live in
:mod:`aeat.domain.justificante`.

Major declaration:

* :func:`parse_justificante` — parse a justificante PDF into its typed
  domain record.
* :func:`parse_justificante_bytes` — parse secure-storage bytes without
  materialising a plaintext file.
"""

from __future__ import annotations

from ._parser import parse_justificante, parse_justificante_bytes

__all__ = [
    "parse_justificante",
    "parse_justificante_bytes",
]
