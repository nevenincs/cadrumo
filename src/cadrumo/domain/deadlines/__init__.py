"""Deadlines: the AEAT filing windows and the engine that resolves them.

Inert namespace. Every contract is reached at its own defining module:
``engine``, ``errors``, ``festivos``, ``models``, ``plazo``, ``profiles``, ``recargo``.

This package re-exported its surface through the namespace. The map is
retired: a consumer names the module that defines what it imports.
"""

from __future__ import annotations

__all__: tuple[str, ...] = ()
