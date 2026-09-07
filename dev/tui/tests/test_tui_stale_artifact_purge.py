"""The bound on the stale-frame sweep, and the race it now survives.

The sweep deletes what a run's manifest does not name. That is the right
question for a frame the run re-rendered and the wrong one for a frame the run
was never asked to render, and the two are indistinguishable from the manifest
alone. What follows pins the difference: the sweep still removes residue, and
it refuses rather than empty a directory whose matrix simply shrank.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from .._artifacts import (
    MAX_STALE_FILES_PER_PURGE,
    Manifest,
    RenderedFrame,
    StaleArtifactPurgeRefusedError,
    now,
    purge_stale_artifacts,
    stale_artifacts,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_REVISION = "a" * 64

_SURFACES = ("home--ready", "ledger--ready", "filing--ready")
_VIEWPORTS = ("small", "medium", "large", "tall")
_THEMES = ("dark", "light")


def _frame(surface: str, viewport: str, theme: str) -> RenderedFrame:
    stem = f"{surface}__{viewport}__{theme}"
    return RenderedFrame(
        surface=surface,
        viewport=viewport,
        columns=120,
        rows=40,
        orientation="landscape",
        theme=theme,
        png=f"png/{stem}.png",
        svg=f"svg/{stem}.svg",
        text=f"text/{stem}.txt",
        png_sha256="0" * 64,
        text_sha256="0" * 64,
        cell_height=22,
    )


def _manifest(frames: tuple[RenderedFrame, ...]) -> Manifest:
    return Manifest(
        source_revision=_REVISION,
        source_revision_at_end=_REVISION,
        generated_at=now(),
        cell_height=22,
        frames=frames,
        failures=(),
        skipped=(),
    )


def _matrix(surfaces: tuple[str, ...]) -> tuple[RenderedFrame, ...]:
    return tuple(
        _frame(surface, viewport, theme) for surface in surfaces for viewport in _VIEWPORTS for theme in _THEMES
    )


def _lay_down(directory: Path, frames: tuple[RenderedFrame, ...]) -> None:
    for kind in ("png", "svg", "text"):
        (directory / kind).mkdir(exist_ok=True)
    for frame in frames:
        (directory / frame.png).write_bytes(b"twenty-five minutes of rendering")
        (directory / frame.svg).write_text("<svg/>", encoding="utf-8")
        (directory / frame.text).write_text("stable text", encoding="utf-8")


def _files(directory: Path) -> set[str]:
    return {path.name for path in directory.rglob("*") if path.is_file()}


def test_a_narrowed_rerender_is_refused_rather_than_emptying_the_directory(tmp_path: Path) -> None:
    """The defect the bound exists for, measured end to end.

    A full render fills the directory. A later run narrowed to one surface
    names a third of it, so every other surface's frames are unclaimed BY
    CONSTRUCTION rather than because anything replaced them, and the sweep
    that reads only the manifest cannot tell the two apart.
    """
    _lay_down(tmp_path, _matrix(_SURFACES))
    before = _files(tmp_path)
    assert len(before) == len(_SURFACES) * len(_VIEWPORTS) * len(_THEMES) * 3

    narrowed = _manifest(_matrix(("ledger--ready",)))

    with pytest.raises(StaleArtifactPurgeRefusedError) as refusal:
        purge_stale_artifacts(tmp_path, narrowed)

    assert "48 unclaimed file(s)" in str(refusal.value)
    assert _files(tmp_path) == before, "a refused sweep must leave the tree exactly as it found it"


def test_the_sweep_still_removes_the_residue_it_was_written_for(tmp_path: Path) -> None:
    """The original check is unchanged: an unclaimed file under the bound goes."""
    frames = _matrix(("ledger--ready",))
    _lay_down(tmp_path, frames)
    (tmp_path / "png" / "left-behind.png").write_bytes(b"")
    (tmp_path / "manifest.json").write_text("{}", encoding="utf-8")

    removed = purge_stale_artifacts(tmp_path, _manifest(frames))

    assert [path.name for path in removed] == ["left-behind.png"]
    assert (tmp_path / frames[0].png).is_file()
    assert (tmp_path / "manifest.json").is_file()
    assert stale_artifacts(tmp_path, _manifest(frames)) == ()


def test_an_explicit_allowance_authorises_the_retirement(tmp_path: Path) -> None:
    """The bound refuses a silent prune, never a declared one."""
    _lay_down(tmp_path, _matrix(_SURFACES))
    narrowed = _manifest(_matrix(("ledger--ready",)))

    removed = purge_stale_artifacts(tmp_path, narrowed, removal_allowance=48)

    assert len(removed) == 48
    assert not (tmp_path / "png" / "home--ready__small__dark.png").exists()
    assert (tmp_path / "png" / "ledger--ready__small__dark.png").is_file()


def test_a_frame_that_vanishes_between_the_listing_and_the_unlink_is_survivable(tmp_path: Path) -> None:
    """The listing and the unlink are separate passes over a slow-moving tree.

    An unguarded unlink turns a benign disappearance into a FileNotFoundError,
    and the sweep runs at the end of a render measured in tens of minutes --
    after every frame is on disk but before the manifest describing them is.
    """
    frames = _matrix(("ledger--ready",))
    _lay_down(tmp_path, frames)
    for name in ("gone.png", "stays.png"):
        (tmp_path / "png" / name).write_bytes(b"")

    doomed = stale_artifacts(tmp_path, _manifest(frames))
    assert {path.name for path in doomed} == {"gone.png", "stays.png"}

    (tmp_path / "png" / "gone.png").unlink()
    removed = purge_stale_artifacts(tmp_path, _manifest(frames))

    assert [path.name for path in removed] == ["stays.png"]
    assert not (tmp_path / "png" / "stays.png").exists()


def test_the_bound_is_one_surface_across_the_full_matrix() -> None:
    """The number is derived, not chosen: 4 viewports x 2 themes x 3 files."""
    assert len(_VIEWPORTS) * len(_THEMES) * 3 == MAX_STALE_FILES_PER_PURGE
