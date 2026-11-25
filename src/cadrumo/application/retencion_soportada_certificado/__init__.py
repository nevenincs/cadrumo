"""Registered operations over the payer certificates behind suffered withholding.

The operator records the figures one payer's certificate states (or declares
them without a certificate), lists the stored records without any tax
identifier, and removes a record. Every write goes through the application's
one write path for the family, which owns the refusals; this package adds only
the exact-profile operation surface around it.

Consumers import from the defining module; the package initializer exports no
symbols.
"""

from __future__ import annotations

__all__: tuple[str, ...] = ()
