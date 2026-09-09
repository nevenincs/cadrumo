"""A frame's recorded appearance is one the renderer can actually produce.

``theme`` completed the ``surface/viewport/theme`` identity a run is diffed
on, and it was the last third of it still typed ``str``. The two words were
written down once, in the command line's own ``THEMES`` tuple, and consulted
only where that command line parsed its ``--theme`` option: nothing that
RECORDED a theme -- not the rendered frame, not the failure, not the skip,
not a manifest read back off disk -- asked whether the word named an
appearance anything had ever been rendered under.

The vocabulary is also a restatement. This package may not import the TUI
entrypoint, so the words are spelled here as well as in the harness that
accepts them and in the application setting they come from. Restating is
allowed; restating with nothing joining the copies is what this file refuses.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from cadrumo.core.config_support import TuiAppearance

from .._artifacts import (
    FailedFrame,
    FrameFailureKind,
    Manifest,
    RenderedFrame,
    SkippedFrame,
    ThemeName,
)
from .._viewports import VIEWPORTS, ViewportName
from ..cli import THEMES, _resolve_themes

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def _frame(theme: str) -> RenderedFrame:
    """A coherent ``small`` frame under ``theme``, and nothing else varied."""
    shape = VIEWPORTS[ViewportName.SMALL]
    return RenderedFrame(
        surface="status",
        viewport=shape.name,
        columns=shape.columns,
        rows=shape.rows,
        orientation=shape.orientation,
        theme=theme,  # type: ignore[arg-type]
        png="png/a.png",
        svg="svg/a.svg",
        text="text/a.txt",
        png_sha256="0" * 64,
        text_sha256="0" * 64,
        cell_height=22,
    )


def test_the_recordable_appearances_are_the_applications_own_minus_auto() -> None:
    """The setting the operator's preference comes from is the other copy.

    ``AUTO`` is the one member deliberately absent: it defers the choice to the
    host terminal, so a frame recorded under it would name no appearance at
    all, and a review has to know which one it is looking at.
    """
    assert set(ThemeName) < {appearance.value for appearance in TuiAppearance}
    assert {appearance.value for appearance in TuiAppearance} - set(ThemeName) == {TuiAppearance.AUTO.value}


def test_auto_is_not_a_theme_a_frame_may_be_recorded_under() -> None:
    """The exclusion is enforced, not merely intended."""
    with pytest.raises(ValidationError):
        _frame(TuiAppearance.AUTO.value)


def test_an_appearance_nothing_was_rendered_under_is_refused_on_every_record() -> None:
    """All three frame records close on the same vocabulary.

    The command line refused an unknown ``--theme``; nothing that took a theme
    without going through the command line did -- and a manifest read back from
    disk never goes through it.
    """
    assert "solarized" not in set(ThemeName)

    with pytest.raises(ValidationError):
        _frame("solarized")
    with pytest.raises(ValidationError):
        FailedFrame(
            surface="status",
            viewport=ViewportName.SMALL,
            theme="solarized",  # type: ignore[arg-type]
            kind=FrameFailureKind.RASTER,
        )
    with pytest.raises(ValidationError):
        SkippedFrame(
            surface="status",
            viewport=ViewportName.SMALL,
            theme="solarized",  # type: ignore[arg-type]
            reason="its surface refused",
        )


def test_a_manifest_read_back_from_disk_carries_the_theme_refusal() -> None:
    """The join must survive serialisation, which is where a manifest arrives."""
    coherent = Manifest(
        generated_at="2026-01-01T00:00:00+00:00",
        source_revision="a" * 64,
        source_revision_at_end="a" * 64,
        cell_height=22,
        frames=tuple(_frame(theme) for theme in ThemeName),
    )
    blob = coherent.model_dump_json()

    assert Manifest.model_validate_json(blob).model_dump_json() == blob, "a coherent manifest must round-trip"
    assert '"theme":"dark"' in blob, "the on-disk spelling stays a plain string, not an enum repr"

    invented = blob.replace('"theme":"dark"', '"theme":"solarized"', 1)
    assert invented != blob, "the substitution must have landed"
    with pytest.raises(ValidationError):
        Manifest.model_validate_json(invented)


def test_the_command_line_offers_the_vocabulary_rather_than_a_second_list() -> None:
    """``THEMES`` is now derived, so it cannot name a word no record accepts."""
    assert tuple(ThemeName) == THEMES
    assert _resolve_themes(None) == THEMES
    assert _resolve_themes(["light"]) == (ThemeName.LIGHT,)

    import typer

    with pytest.raises(typer.BadParameter, match="unknown theme 'solarized'"):
        _resolve_themes(["solarized"])
