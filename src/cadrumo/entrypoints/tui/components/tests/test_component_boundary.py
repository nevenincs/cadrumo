"""Boundary proofs for the canonical TUI presentation-component package."""

from __future__ import annotations

import pytest

from .....core.presentation import FormField
from ..dialogs import TextEditScreen
from ..errors import ErrorPanel
from ..logs import BoundedLogPanel
from ..status import PinnedStatusBar
from ..theme import install_cadrumo_themes
from ..widgets import ContentDataTable

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


def test_presentation_symbols_have_one_direct_canonical_home() -> None:
    """Consumers import reusable presentation mechanics from their defining module."""
    assert tuple(
        symbol.__module__
        for symbol in (TextEditScreen, ErrorPanel, FormField, BoundedLogPanel, PinnedStatusBar, ContentDataTable)
    ) == (
        "cadrumo.entrypoints.tui.components.dialogs",
        "cadrumo.entrypoints.tui.components.errors",
        "cadrumo.core.presentation",
        "cadrumo.entrypoints.tui.components.logs",
        "cadrumo.entrypoints.tui.components.status",
        "cadrumo.entrypoints.tui.components.widgets",
    )
    assert install_cadrumo_themes.__module__ == "cadrumo.entrypoints.tui.components.theme"
