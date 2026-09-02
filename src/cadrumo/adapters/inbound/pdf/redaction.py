"""The label that stands in for a PDF path in anything a person can read.

Diagnostics, logs and error messages must not carry the filename of a document
a taxpayer supplied: the name alone can disclose who they are, which return it
is, or where it was stored. Every inbound PDF surface therefore reports this
label instead of the path.

It is declared once because eight modules previously declared it separately, and
a redaction token that eight places have to agree on is a token that will
eventually disagree — at which point one surface leaks a filename and nothing
fails.
"""

from __future__ import annotations

from typing import Final

__all__ = ["INPUT_PDF_SOURCE_LABEL"]

INPUT_PDF_SOURCE_LABEL: Final = "<input-pdf>"
"""Stands in for the source PDF path wherever a message could be read or stored."""
