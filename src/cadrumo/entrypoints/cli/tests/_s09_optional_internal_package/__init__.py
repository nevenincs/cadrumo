"""Installed optional-package fixture with one broken internal import."""

from __future__ import annotations

__import__(f"{__name__}.broken_internal")
