"""Shared pytest collection hook enforcing the hexagonal marker taxonomy.

This module is test-infrastructure, not a production module. It is imported
from both the repo-root ``conftest.py`` and ``src/aeat/tests/conftest.py``
so that items collected anywhere under ``src/aeat/`` pass through the same
enforcement surface.

Contract enforced by :func:`apply` on every collected item:

- Each item must carry exactly one execution marker from
  ``{unit, integration, aeat_live}``. Zero or more than one raises
  :class:`pytest.UsageError`.
- Each item must carry exactly one accepted ``hex_*`` marker at module level.

Double-invocation tolerance: the repo-root ``conftest.py`` and the
package-scoped ``src/aeat/tests/conftest.py`` both delegate to
:func:`apply`. Items may pass through the hook twice; this is safe
because :func:`apply` enforces invariants on items it receives and
filters ``items`` in-place. A second pass over already-validated items
is a no-op because their marker sets are identical.

Live AEAT access is opt-in gated by the package-scoped conftest after
this taxonomy check.
"""

from __future__ import annotations

import pytest

_EXECUTION_MARKERS = frozenset({"unit", "integration", "aeat_live"})
_HEX_MARKERS = frozenset(
    {
        "hex_application",
        "hex_core",
        "hex_domain",
        "hex_entrypoint",
        "hex_inbound_adapter",
        "hex_outbound_adapter",
        "hex_persistence_adapter",
    },
)


def apply(config: pytest.Config, items: list[pytest.Item]) -> None:
    """Apply the hexagonal marker taxonomy contract to the collected items.

    Raises :class:`pytest.UsageError` for items missing exactly one execution
    marker or exactly one accepted hexagonal architecture marker.

    Args:
        config: The active :class:`pytest.Config` from the collection hook.
        items: The mutable collection items list; filtered in-place.
    """
    remaining: list[pytest.Item] = []
    for item in items:
        owned = {m.name for m in item.iter_markers()}
        execution = owned & _EXECUTION_MARKERS
        if len(execution) != 1:
            raise pytest.UsageError(
                f"{item.nodeid}: must carry exactly one of {{unit, integration, aeat_live}}, "
                f"found {sorted(execution) or 'none'}",
            )
        hex_markers = {name for name in owned if name.startswith("hex_")}
        if len(hex_markers) != 1 or not hex_markers <= _HEX_MARKERS:
            raise pytest.UsageError(
                f"{item.nodeid}: must carry exactly one accepted hex_* marker, found {sorted(hex_markers) or 'none'}",
            )
        remaining.append(item)
    items[:] = remaining
