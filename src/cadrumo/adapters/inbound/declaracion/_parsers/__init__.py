"""Inert namespace for declaración PDF parser backends.

The public parser imports text extraction directly from the active backend
:mod:`adapters.inbound.declaracion._parsers.pdfplumber_backend`, which tries
a canary-guarded pypdfium2 fast path first, then falls back to the shared
pdfplumber primitive used by the other inbound PDF adapters.

The package initializer exports no functions.
"""

from __future__ import annotations

__all__: tuple[str, ...] = ()
