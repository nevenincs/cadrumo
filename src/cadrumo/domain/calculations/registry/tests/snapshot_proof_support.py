"""Observation of the snapshot validator's cross-check registry for proof tests."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import replace

import pytest

from .. import snapshot as snapshot_module


def count_cross_checks(monkeypatch: pytest.MonkeyPatch) -> list[int]:
    """Wrap every registered cross-check so it counts its calls and still runs the real check.

    The returned list holds one counter per registry entry, in registry
    order. The wrapper replaces the registry for the test's duration only.
    """
    registry = snapshot_module._SNAPSHOT_CROSS_CHECKS
    counts = [0] * len(registry)

    def counted(index: int, run: Callable[..., None]) -> Callable[..., None]:
        def run_and_count(context: object) -> None:
            counts[index] += 1
            run(context)

        return run_and_count

    monkeypatch.setattr(
        snapshot_module,
        "_SNAPSHOT_CROSS_CHECKS",
        tuple(replace(check, run=counted(index, check.run)) for index, check in enumerate(registry)),
    )
    return counts
