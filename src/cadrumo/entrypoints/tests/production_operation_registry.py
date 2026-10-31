"""Own the once-per-process production operation registry shared by read-only tests."""

from __future__ import annotations

from functools import cache

from ...application.operations.registry import OperationRegistry
from ..operation_composition import build_production_operation_registry


@cache
def production_operation_registry() -> OperationRegistry:
    """Compose the production registry once per process for tests that only look definitions up.

    The registry is a frozen model of immutable definitions; tests that assert on
    composition itself, pass composition arguments or scope the build call the
    builder directly.
    """
    return build_production_operation_registry()
