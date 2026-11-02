"""The bound an invoice holds a counterparty's name to when one is entered."""

from __future__ import annotations

from typing import Final

INVOICE_COUNTERPARTY_NAME_MAX_LENGTH: Final = 256
"""The most characters a counterparty name takes on entry.

The Modelo 347 party binding carries the name at this same width, so a name entered
within it is one the declaration can relate. A name stored before this bound still reads.
"""

__all__ = ["INVOICE_COUNTERPARTY_NAME_MAX_LENGTH"]
