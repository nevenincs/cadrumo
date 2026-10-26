"""Inert namespace for declaración PDF parser backends.

The public parser imports text extraction directly from the active backend
:mod:`adapters.inbound.declaracion._parsers.pdfplumber_backend`, which reads
page text through the shared pdfplumber primitives used by the other inbound
PDF adapters.

The package initializer exports no functions.
"""

from __future__ import annotations

__all__: tuple[str, ...] = ()
