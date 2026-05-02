"""Re-export of identifier value types consumed by the deadline domain.

Centralises the :class:`aeat.domain._identifiers.ModeloIdentifier` import so
modules under :mod:`aeat.domain.deadlines` need not reach into a sibling
package.
"""

from __future__ import annotations

from .._identifiers import ModeloIdentifier

__all__ = ["ModeloIdentifier"]
