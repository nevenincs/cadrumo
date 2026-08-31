"""PDF backend facade for the declaración parser.

The public parser imports text extraction through this package so path-based
and bytes-based declaration-copy parsing stay paired. The active backend is
:mod:`adapters.inbound.declaracion._parsers._pdfplumber_backend`: it tries
a canary-guarded pypdfium2 fast path first, then falls back to the shared
pdfplumber primitive used by the other inbound PDF adapters.

Future backends can be added behind the same two exported functions without
changing the registry-profile parser in
:mod:`adapters.inbound.declaracion._parser`.
"""

from __future__ import annotations

__all__: tuple[str, ...] = ()
