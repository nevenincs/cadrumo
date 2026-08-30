"""Buckets: the profile-scoped encrypted stores and their lifecycle events.

Inert namespace. Every contract is reached at its own defining module:
``errors``, ``event``, ``event_repository``, ``protocols``.

This package re-exported its surface through the namespace. The map is
retired: a consumer names the module that defines what it imports.
"""

from __future__ import annotations

__all__: tuple[str, ...] = ()
