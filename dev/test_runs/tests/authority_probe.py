"""Child-pytest probe that reads the process-shared registry authority, as a registry test does.

The run that selects it freezes its own snapshot below the configured
temporary-storage root, beside the collection root. Armed with
``CADRUMO_AUTHORITY_PROBE_LEAK_LEASE=1`` it leaves its lease open past the
session, which is what a test that forgot to close one does.
"""

from __future__ import annotations

import os
from contextlib import ExitStack
from pathlib import Path

import pytest

from cadrumo.domain.calculations.registry.authority import bundled_indexed_authority

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

LEAK_LEASE_ENV = "CADRUMO_AUTHORITY_PROBE_LEAK_LEASE"

_LEAKED_LEASES = ExitStack()
"""Holds an armed probe's lease for the rest of the process."""


def test_reads_the_shared_authority_from_the_controlled_temporary_root() -> None:
    """Open the frozen snapshot through the shared owner, as runtime reads it."""
    authority_root = Path(os.environ["CADRUMO_AUTHORITY_ROOT"]).resolve()
    temporary_root = Path(os.environ["CADRUMO_TEMP_DIR"]).resolve()
    assert authority_root.is_relative_to(temporary_root), f"{authority_root} is not under {temporary_root}"

    if os.environ.get(LEAK_LEASE_ENV) == "1":
        operation = _LEAKED_LEASES.enter_context(bundled_indexed_authority().operation())
        assert operation.pin().logical_generation
        return
    with bundled_indexed_authority().operation() as operation:
        assert operation.pin().logical_generation
