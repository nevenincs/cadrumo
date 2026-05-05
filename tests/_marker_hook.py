"""Shared pytest collection hook enforcing the nine-marker taxonomy.

This module is test-infrastructure, not a production module. It is imported
from both the repo-root ``conftest.py`` and ``tests/conftest.py`` so that
items collected under ``src/aeat/`` and ``tests/`` alike pass through the
same enforcement surface.

Contract enforced by :func:`apply` on every collected item:

- Each item must carry exactly one access marker from
  ``{unit, live_read, live_write}``. Zero or more than one raises
  :class:`pytest.UsageError`.
- Each item must carry at least one ``domain_*`` marker at module level.
- Items carrying ``live_write`` are always DROPPED (not skipped) from
  collection. There is no bypass.

Drop-not-skip semantics exist because charter ``#116`` rule ``R1`` demands
structural invisibility for the live-write path, not visible deferral:
skipped items still surface in reports as would-have-run deferrals and
are one env-var flip from executing.

Double-invocation tolerance: the repo-root ``conftest.py`` and the
``tests/conftest.py`` both delegate to :func:`apply`. Items collected
under ``tests/`` may pass through the hook twice. This is safe because
:func:`apply` enforces invariants on items it receives and filters
``items`` in-place; a second pass over already-validated items is a
no-op because their marker sets are identical.

The hook never consults write-enable environment variables. Live AEAT
writes are permanently forbidden.
"""

from __future__ import annotations

import pytest

_ACCESS_MARKERS = frozenset({"unit", "live_read", "live_write"})


def apply(config: pytest.Config, items: list[pytest.Item]) -> None:
    """Apply the nine-marker taxonomy contract to the collected items.

    Raises :class:`pytest.UsageError` for items missing exactly one access
    marker or at least one domain marker. Drops every ``live_write`` item.
    Emits a single session-level warning when the first ``live_write`` drop
    occurs.

    Args:
        config: The active :class:`pytest.Config` from the collection hook.
        items: The mutable collection items list; filtered in-place.
    """
    remaining: list[pytest.Item] = []
    warned = False
    for item in items:
        owned = {m.name for m in item.iter_markers()}
        access = owned & _ACCESS_MARKERS
        if len(access) != 1:
            raise pytest.UsageError(
                f"{item.nodeid}: must carry exactly one of "
                f"{{unit, live_read, live_write}}, found {sorted(access) or 'none'}"
            )
        if not any(name.startswith("domain_") for name in owned):
            raise pytest.UsageError(f"{item.nodeid}: must carry at least one domain_* marker")
        if "live_write" in access:
            if not warned:
                config.issue_config_time_warning(
                    pytest.PytestWarning(
                        "live_write items dropped at collection; live AEAT writes are permanently forbidden"
                    ),
                    stacklevel=2,
                )
                warned = True
            continue
        remaining.append(item)
    items[:] = remaining
