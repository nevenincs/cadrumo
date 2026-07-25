"""Shared pytest collection hook enforcing the hexagonal marker taxonomy.

This module is test-infrastructure, not a production module. It is imported
from both the repo-root ``conftest.py`` and ``src/cadrumo/tests/conftest.py``
so that items collected anywhere under ``src/cadrumo/`` pass through the same
enforcement surface.

Contract enforced by :func:`apply` on every collected item:

- Each item must carry exactly one execution marker from
  ``{unit, integration, aeat_live}``. Zero or more than one raises
  :class:`pytest.UsageError`.
- Each item must carry exactly one accepted ``hex_*`` marker at module level.
- A ``serial`` item is held out of any run with xdist workers active, and the
  hold is announced.

The ``serial`` hold exists because the marker was otherwise inert. pytest-xdist
has no notion of it -- its only scheduling primitive is ``--dist=loadgroup``
plus ``xdist_group`` -- so nothing enforced the marker's own contract ("must run
without xdist workers"). It was honoured solely by the justfile splitting the
integration lane into a ``not serial`` parallel pass and a ``-n0`` serial pass;
any other invocation (a bare ``pytest -m integration``, a path-scoped run) ran
isolation-sensitive tests against a run-varying set of co-resident files and
produced failures that belonged to the schedule, not the code.

The hold is a deselect plus a warning rather than a refusal, and both halves are
load-bearing. Raising from this hook is not available: under xdist this hook runs
INSIDE each worker, and an exception here kills the worker, which xdist reports as
``INTERNALERROR ... assert not crashitem`` -- the same class of aborted run the
hold exists to prevent. A silent deselect is not available either: xdist performs
deselection inside its workers and the controller's stats never receive it (see
:mod:`._deselection_hook`), so the dropped coverage would go unreported. The
warning rides the warnings channel, which IS aggregated to the controller, so the
hold is always stated.

Double-invocation tolerance: the repo-root ``conftest.py`` and the
package-scoped ``src/cadrumo/tests/conftest.py`` both delegate to
:func:`apply`. Items may pass through the hook twice; this is safe
because :func:`apply` enforces invariants on items it receives and
filters ``items`` in-place. A second pass over already-validated items
is a no-op because their marker sets are identical.

Live AEAT access is opt-in gated by the package-scoped conftest after
this taxonomy check.
"""

from __future__ import annotations

import warnings

import pytest

_EXECUTION_MARKERS = frozenset({"unit", "integration", "aeat_live"})
_SERIAL_MARKER = "serial"
_MAX_NAMED_HELD_ITEMS = 10

SERIAL_HELD_WORKEROUTPUT_KEY = "cadrumo_serial_held"
"""``config.workeroutput`` key carrying the node ids held out of an xdist run."""


class SerialTestsHeldWarning(pytest.PytestWarning):
    """Announces ``serial`` items held out of a run with xdist workers active."""


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
    _hold_serial_items_from_xdist(config, items)


def _hold_serial_items_from_xdist(config: pytest.Config, items: list[pytest.Item]) -> None:
    """Deselect ``serial`` items when xdist workers are active, and say so.

    ``config.workerinput`` is present only inside an xdist worker, and is the
    signal that holds up: a worker reports ``numprocesses`` as ``None`` (the
    controller's value does not travel), so the worker-input probe -- not the
    worker count -- is what distinguishes a distributed run from ``-n0``.

    Args:
        config: The active :class:`pytest.Config` from the collection hook.
        items: The mutable collection items list; filtered in-place.
    """
    if not hasattr(config, "workerinput"):
        return
    held = [item for item in items if item.get_closest_marker(_SERIAL_MARKER) is not None]
    if not held:
        return
    items[:] = [item for item in items if item.get_closest_marker(_SERIAL_MARKER) is None]
    config.hook.pytest_deselected(items=held)

    node_ids = sorted(item.nodeid for item in held)
    # ``workeroutput`` is the sanctioned worker-to-controller channel; xdist
    # ships it on node-down, where ``pytest_testnodedown`` can read it. Written
    # here so a controller-side hook can turn the hold into a non-zero exit
    # rather than leaving a green run that silently dropped tests. Inert until
    # such a hook exists: nothing reads the key yet.
    config.workeroutput[SERIAL_HELD_WORKEROUTPUT_KEY] = node_ids
    named = ", ".join(node_ids[:_MAX_NAMED_HELD_ITEMS])
    elided = len(node_ids) - _MAX_NAMED_HELD_ITEMS
    if elided > 0:
        named = f"{named}, and {elided} more"
    warnings.warn(
        f"Held {len(node_ids)} serial-marked test(s) out of this run because xdist workers are active; "
        f"they did NOT execute: {named}. "
        "Serial tests mutate or read process-global state and must run with no workers. "
        "Run them with `just test-integration-serial`, or add -n0 to this invocation.",
        SerialTestsHeldWarning,
        stacklevel=1,
    )
