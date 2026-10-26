"""Shared test support for the outbound AEAT adapter packages.

Holds helpers used by more than one of the sibling test packages beneath
``adapters/outbound/aeat`` (``auth/tests``, ``browser/tests``, ``sede/tests``).
A helper needed by only one of them belongs in that package's own
``tests/_*_support.py``, not here.

Shared helpers live in public defining modules such as ``process_support`` so
sibling test packages can import their owner directly.  This package marker is
inert; repository-wide private and forwarding imports are owned by
``just check-import-boundaries``.
"""

from __future__ import annotations

__all__: tuple[str, ...] = ()
