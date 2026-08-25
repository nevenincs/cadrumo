"""Boundary proofs for canonical TUI presentation components."""

from __future__ import annotations

import pytest

import cadrumo.entrypoints.tui.components as components
from cadrumo.entrypoints.tui.components.dialogs import TextEditScreen
from cadrumo.entrypoints.tui.components.errors import ErrorPanel
from cadrumo.entrypoints.tui.components.forms import FormField
from cadrumo.entrypoints.tui.components.logs import BoundedLogPanel
from cadrumo.entrypoints.tui.components.status import PinnedStatusBar
from cadrumo.entrypoints.tui.components.theme import install_cadrumo_themes
from cadrumo.entrypoints.tui.components.widgets import ContentDataTable

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
        "cadrumo.entrypoints.tui.components.forms",
        "cadrumo.entrypoints.tui.components.logs",
        "cadrumo.entrypoints.tui.components.status",
        "cadrumo.entrypoints.tui.components.widgets",
    )
    assert install_cadrumo_themes.__module__ == "cadrumo.entrypoints.tui.components.theme"
