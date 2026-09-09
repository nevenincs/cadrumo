"""Behaviour tests for the core wizard catalogue registration boundary."""

from __future__ import annotations

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def test_setup_flow_round_trip_identity() -> None:
    """get_setup_flow() returns the exact SETUP_FLOW object from _catalogue."""

    # Import catalogue first — its module body calls register_wizard_catalogue.
    from ...application.wizard import catalogue as catalogue
    from ..wizard_catalogue import get_setup_flow

    assert get_setup_flow() is catalogue.SETUP_FLOW, (
        "get_setup_flow() must return the identical SETUP_FLOW object "
        "that _catalogue registered — got a different object"
    )


def test_setup_flow_id_is_setup() -> None:
    """The registered SETUP_FLOW carries the canonical 'setup' identifier."""

    from ..wizard_catalogue import get_setup_flow

    flow = get_setup_flow()
    assert flow.id == "setup", f"Expected flow.id == 'setup', got {flow.id!r}"

