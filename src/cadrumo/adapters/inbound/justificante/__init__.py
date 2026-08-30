"""Inbound parser adapter for AEAT justificante receipt PDFs.

Parses the receipt PDF AEAT issues after a filing into the strict
:class:`domain.justificante.Justificante` domain record used by
reconciliation and evidence workflows. A justificante is receipt metadata
(CSV, modelo, period, taxpayer, timestamp, totals, verification URL), not the
casilla-complete filing copy handled by
:mod:`adapters.inbound.declaracion`.

Both public entry points keep the receipt boundary narrow: the filesystem route
hashes the PDF and the bytes route supports secure-storage captures without
materialising plaintext scratch files. The field extraction discipline and
structured :class:`domain.justificante.JustificanteParseError`
attributes live below this package boundary.

Major declaration:

* :func:`parse_justificante` — parse a justificante PDF into its typed
  domain record.
* :func:`parse_justificante_bytes` — parse secure-storage bytes without
  materialising a plaintext file.
"""

from __future__ import annotations

from .parser import parse_justificante, parse_justificante_bytes

__all__ = [
    "parse_justificante",
    "parse_justificante_bytes",
]
