"""Behaviour tests for the core wizard catalogue registration boundary."""

from __future__ import annotations

import pytest

from cadrumo.application.wizard.catalogue import build_setup_flow
from cadrumo.application.wizard.models import WizardFlow
from cadrumo.core.wizard_catalogue import get_setup_flow, register_wizard_catalogue
from cadrumo.domain.calculations.registry.authority import PinnedAuthorityOperation

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


@pytest.fixture(scope="module")
def registered_setup_flow(operation: PinnedAuthorityOperation) -> WizardFlow:
    """Register one operation-built application descriptor for this module."""
    flow = build_setup_flow(operation)
    register_wizard_catalogue(flow)
    return flow


def test_setup_flow_round_trip_identity(registered_setup_flow: WizardFlow) -> None:
    """get_setup_flow() returns the exact descriptor registered by the application."""
    assert get_setup_flow() is registered_setup_flow


def test_setup_flow_id_is_setup(registered_setup_flow: WizardFlow) -> None:
    """The registered SETUP_FLOW carries the canonical 'setup' identifier."""
    assert registered_setup_flow.id == "setup", f"Expected flow.id == 'setup', got {registered_setup_flow.id!r}"
