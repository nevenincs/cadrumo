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
    """Ensure the wizard `SETUP_FLOW` catalogue is registered for the session.

    `taxpayer_profile_from_mapping` reads `get_setup_flow()`, which raises
    `WizardCatalogueNotRegisteredError` until the application layer has
    registered the catalogue. Importing `aeat.application.wizard._catalogue`
    triggers that registration as an import-time side effect, so the
    projection resolves for every test in this package regardless of run
    selection.
    """
    import aeat.application.wizard._catalogue  # noqa: F401  (import for registration side effect)
