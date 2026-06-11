"""Pytest fixtures for `domain/deadlines/` tests.

The deadline profile projection (`taxpayer_profile_from_mapping`) reads
the wizard `SETUP_FLOW` descriptor via the `wizard_catalogue` slot so
canonical-token semantics for every boolean / select / text field stay
in lockstep with the wizard's on-prompt validation. The catalogue is
registered by the application layer at startup; importing
`aeat.application.wizard._catalogue` triggers the registration as an
import-time side effect.

These tests exercise the projection directly, so the catalogue must be
registered before any test in this package runs. The autouse session-
scoped fixture imports the catalogue once per session.
"""

from __future__ import annotations

import pytest


@pytest.fixture(autouse=True, scope="session")
def _register_wizard_catalogue() -> None:
    """Ensure the wizard `SETUP_FLOW` catalogue is registered for the session."""
