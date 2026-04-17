"""Typing-only Protocol placeholders for sibling packages not yet on main."""

from __future__ import annotations

from typing import Protocol


class SupportsAttachmentId(Protocol):
    """Minimum typing surface for a future attachment reference (#76)."""

    attachment_id: str


class SupportsTaxCategoryId(Protocol):
    """Minimum typing surface for a future tax-category reference (#77)."""

    category_id: str
