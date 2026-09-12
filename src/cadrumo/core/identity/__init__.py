"""Inert identity namespace.

Identity definitions live in focused public modules. Consumers import those
defining modules directly; this package intentionally exposes no barrel names.
"""

from __future__ import annotations

__all__: tuple[str, ...] = ()
