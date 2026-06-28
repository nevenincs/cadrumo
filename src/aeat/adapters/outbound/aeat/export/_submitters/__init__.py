"""Empty package: no AEAT remote submitter surface is exposed.

Live AEAT submission and write-shaped portal walks are permanently
forbidden. This package intentionally exports no submitter ABC and
no browser-session contract; ``__all__`` is the empty list so any
star import surfaces nothing and any attribute access fails fast.
"""

from __future__ import annotations

__all__: list[str] = []
