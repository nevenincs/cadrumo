"""Spending and income categories, and the taxonomy that classifies them.

Inert namespace. Every contract is reached at its own defining module:
``corpus``, ``errors``, ``profile``, ``proportionality``, ``registry``, ``spending_category``.

This package re-exported its surface through the namespace. The map is
retired: a consumer names the module that defines what it imports.
"""

from __future__ import annotations

__all__: tuple[str, ...] = ()
