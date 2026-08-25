"""Canonical secret-entry presentation namespace.

Secret screens are imported from their owning modules. The namespace facade
is intentionally inert so it cannot become a second authority or retain a
long-lived presentation object.
"""

from __future__ import annotations

__all__: tuple[str, ...] = ()
