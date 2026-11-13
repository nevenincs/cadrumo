"""Registered operations over the pension contribution certificate records.

The operator records the contribution one certificate states for one plan, clave
and subclave, corrects it under the revision a list showed, lists the stored
records without any tax identifier, and removes a record. Every write goes
through the application's one write path for the family, which owns the
refusals; this package adds only the exact-profile operation surface around it.

Consumers import from the defining module; the package initializer exports no
symbols.
"""

from __future__ import annotations

__all__: tuple[str, ...] = ()
