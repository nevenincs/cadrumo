"""Boundary proofs for canonical TUI presentation components."""

from __future__ import annotations

import pytest
import cadrumo.entrypoints.tui.components as components

from .....core.presentation import FormField
from ..dialogs import TextEditScreen
from ..errors import ErrorPanel
from ..logs import BoundedLogPanel
from ..status import PinnedStatusBar
from ..theme import install_cadrumo_themes
from ..widgets import ContentDataTable

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


def test_components_facade_is_inert() -> None:
    """Presentation symbols are never republished through the package facade."""
    assert components.__all__ == ()
    assert all(
        not hasattr(components, symbol.__name__)
        for symbol in (TextEditScreen, ErrorPanel, FormField, BoundedLogPanel, PinnedStatusBar, ContentDataTable)
    )
    assert not hasattr(components, install_cadrumo_themes.__name__)


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
