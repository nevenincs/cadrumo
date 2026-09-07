"""A frame's recorded grid is joined to the viewport it names.

``columns``, ``rows`` and ``orientation`` restate what ``_viewports`` already
decides for a named viewport, so the manifest carried the same concept twice
with nothing forcing the two to agree. They disagreed in this suite's own
fixtures: six helpers built ``viewport="small"`` frames at 120x40 -- the
medium grid -- and every gate over them reported clean, because no code
anywhere compared the recorded shape against the named one.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from .._artifacts import FailedFrame, FrameFailureKind, Manifest, RenderedFrame, SkippedFrame
from .._viewports import VIEWPORTS, Orientation, ViewportName

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def _frame(
    *,
    viewport: str = ViewportName.SMALL,
    columns: int | None = None,
    rows: int | None = None,
    orientation: str | None = None,
) -> RenderedFrame:
    """A coherent frame at ``viewport``, before whatever the caller contradicts.

    Every geometry argument defaults to what the named viewport owns, so a
    test states only the disagreement it means to introduce.
    """
    shape = VIEWPORTS[ViewportName(viewport)]
    return RenderedFrame(
        surface="status",
        viewport=ViewportName(viewport),
        columns=shape.columns if columns is None else columns,
        rows=shape.rows if rows is None else rows,
        orientation=shape.orientation if orientation is None else Orientation(orientation),
        theme="dark",
        png="png/a.png",
        svg="svg/a.svg",
        text="text/a.txt",
        png_sha256="0" * 64,
        text_sha256="0" * 64,
        cell_height=22,
    )


def test_every_viewport_the_module_owns_records_coherently() -> None:
    """The positive direction: no real grid may be refused.

    A join that refuses the shapes the renderer actually produces is worse
    than no join, so this asserts the whole owned set round-trips before any
    of the refusals below are trusted.
    """
    for name, shape in VIEWPORTS.items():
        frame = _frame(viewport=name, columns=shape.columns, rows=shape.rows, orientation=shape.orientation)
        assert frame.key == f"status/{name}/dark"
        assert frame.orientation is shape.orientation


def test_a_grid_that_contradicts_the_named_viewport_is_refused() -> None:
    """The defect this gate was written for, as the fixtures really had it.

    ``small`` at 120x40 was what six helpers in this package built. It is a
    statement about pixels on disk that the frames do not support, and it
    validated cleanly under the previous declaration.
    """
    medium = VIEWPORTS[ViewportName.MEDIUM]

    with pytest.raises(ValidationError, match="but viewport small is"):
        _frame(columns=medium.columns, rows=medium.rows)


def test_an_orientation_the_grid_does_not_produce_is_refused() -> None:
    """``small`` is landscape by its own arithmetic; recording otherwise lies."""
    with pytest.raises(ValidationError, match="but viewport small is"):
        _frame(orientation=Orientation.PORTRAIT)


def test_a_viewport_this_module_never_named_is_refused_on_every_record() -> None:
    """All three frame records close on the same vocabulary.

    ``resolve`` already refused an unknown grid, but nothing that took a name
    without going through it did -- and a manifest read back from disk never
    goes through it.
    """
    assert "enormous" not in set(VIEWPORTS)

    with pytest.raises(ValidationError):
        RenderedFrame(
            surface="status",
            viewport="enormous",  # type: ignore[arg-type]
            columns=80,
            rows=24,
            orientation=Orientation.LANDSCAPE,
            theme="dark",
            png="png/a.png",
            svg="svg/a.svg",
            text="text/a.txt",
            png_sha256="0" * 64,
            text_sha256="0" * 64,
            cell_height=22,
        )
    with pytest.raises(ValidationError):
        FailedFrame(surface="status", viewport="enormous", theme="dark", kind=FrameFailureKind.RASTER)
    with pytest.raises(ValidationError):
        SkippedFrame(surface="status", viewport="enormous", theme="dark", reason="its surface refused")


def test_a_manifest_read_back_from_disk_carries_the_same_refusals() -> None:
    """The join must survive serialisation, which is where a manifest arrives.

    A validator that only fires on in-process construction leaves the file on
    disk exactly as unchecked as it was.
    """
    coherent = Manifest(
        generated_at="2026-01-01T00:00:00+00:00",
        source_revision="a" * 64,
        source_revision_at_end="a" * 64,
        cell_height=22,
        frames=tuple(
            _frame(viewport=name, columns=shape.columns, rows=shape.rows, orientation=shape.orientation)
            for name, shape in VIEWPORTS.items()
        ),
        failures=(
            FailedFrame(surface="status", viewport=ViewportName.TALL, theme="dark", kind=FrameFailureKind.RASTER),
        ),
        skipped=(SkippedFrame(surface="status", viewport=ViewportName.TALL, theme="dark", reason="refused"),),
    )
    blob = coherent.model_dump_json()

    assert Manifest.model_validate_json(blob).model_dump_json() == blob, "a coherent manifest must round-trip"
    assert '"viewport":"small"' in blob, "the on-disk spelling stays a plain string, not an enum repr"

    incoherent = blob.replace('"columns":80,"rows":24', '"columns":200,"rows":50', 1)
    assert incoherent != blob, "the substitution must have landed"
    with pytest.raises(ValidationError, match="but viewport small is"):
        Manifest.model_validate_json(incoherent)
