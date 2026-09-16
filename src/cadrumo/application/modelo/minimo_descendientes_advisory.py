"""Shared bound for Modelo 100 mínimo por descendientes diagnostic copy.

The registry-facing collection seams and their message builders live in the
sibling private module; this public owner holds the cap that the
calculate-input diagnostic renderer also applies.
"""

from __future__ import annotations

__all__ = ["MAX_NAMED_DESCENDANTS"]

# The interpolated descendant list is the only unbounded term in these
# operator-facing messages. Keep the shared cap in this public owner so the
# calculate-input diagnostic renderer uses the same bound.
MAX_NAMED_DESCENDANTS = 3
