"""The review catalogue follows a run while a render is still writing it.

A render writes each PNG in place over more than an hour and its manifest only
at the end, so the catalogue must publish frames from the directory alone,
never publish a file mid-write, and attach manifest readings only to the exact
pixels they were recorded against. The clock is injected so settling is
proven without sleeping.
"""

from __future__ import annotations

import os
from hashlib import sha256
from pathlib import Path

import pytest
from PIL import Image

from .._artifacts import MANIFEST_NAME, Manifest, RenderedFrame, ThemeName, write_manifest
from .._review_catalogue import SETTLE_SECONDS, ReviewCatalogue, parse_stem
from .._viewports import VIEWPORTS, ViewportName

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_NOW = 1_900_000_000.0
_REVISION = "c" * 64


class _Clock:
    def __init__(self) -> None:
        self.now = _NOW

    def __call__(self) -> float:
        return self.now


def _write_png(path: Path, colour: tuple[int, int, int], *, size: tuple[int, int] = (40, 20)) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", size, colour).save(path, format="PNG")
    return sha256(path.read_bytes()).hexdigest()


def _modified(path: Path, at: float) -> None:
    os.utime(path, (at, at))


def _frame_path(runs: Path, stem: str, run: str = "current") -> Path:
    return runs / run / "png" / f"{stem}.png"


def _settled_frame(runs: Path, stem: str, colour: tuple[int, int, int], run: str = "current") -> str:
    path = _frame_path(runs, stem, run)
    digest = _write_png(path, colour)
    _modified(path, _NOW - SETTLE_SECONDS - 1)
    return digest


def test_a_frame_is_published_only_once_its_file_has_stopped_changing(tmp_path: Path) -> None:
    clock = _Clock()
    catalogue = ReviewCatalogue(tmp_path, clock=clock)
    path = _frame_path(tmp_path, "home--ready__small__dark")
    digest = _write_png(path, (10, 20, 30))
    _modified(path, _NOW - 0.2)

    catalogue.refresh()
    view = catalogue.run("current")

    assert view is not None
    assert view.frames == ()

    clock.now = _NOW + SETTLE_SECONDS

    assert catalogue.refresh() is True
    view = catalogue.run("current")
    assert view is not None
    (frame,) = view.frames
    assert (frame.key, frame.png_sha256, frame.width, frame.height) == ("home--ready/small/dark", digest, 40, 20)
    assert catalogue.refresh() is False


def test_a_rewrite_in_progress_keeps_the_last_settled_image_until_it_settles(tmp_path: Path) -> None:
    clock = _Clock()
    catalogue = ReviewCatalogue(tmp_path, clock=clock)
    first = _settled_frame(tmp_path, "home--ready__small__dark", (10, 20, 30))
    catalogue.refresh()

    path = _frame_path(tmp_path, "home--ready__small__dark")
    second = _write_png(path, (200, 20, 30))
    _modified(path, _NOW - 0.1)

    assert catalogue.refresh() is False
    view = catalogue.run("current")
    assert view is not None
    assert view.frames[0].png_sha256 == first

    clock.now = _NOW + SETTLE_SECONDS

    assert catalogue.refresh() is True
    view = catalogue.run("current")
    assert view is not None
    assert view.frames[0].png_sha256 == second != first


def test_a_frame_removed_from_disk_leaves_the_catalogue(tmp_path: Path) -> None:
    catalogue = ReviewCatalogue(tmp_path, clock=_Clock())
    _settled_frame(tmp_path, "home--ready__small__dark", (1, 2, 3))
    _settled_frame(tmp_path, "home--ready__small__light", (4, 5, 6))
    catalogue.refresh()

    _frame_path(tmp_path, "home--ready__small__dark").unlink()

    assert catalogue.refresh() is True
    view = catalogue.run("current")
    assert view is not None
    assert [frame.stem for frame in view.frames] == ["home--ready__small__light"]


def test_png_files_that_do_not_name_a_frame_are_reported_and_never_published(tmp_path: Path) -> None:
    catalogue = ReviewCatalogue(tmp_path, clock=_Clock())
    for stem in ("probe", "home__enormous__dark", "home__small__sepia", "__small__dark"):
        _settled_frame(tmp_path, stem, (9, 9, 9))

    catalogue.refresh()
    view = catalogue.run("current")

    assert view is not None
    assert view.frames == ()
    assert view.unrecognised == tuple(
        sorted(f"{stem}.png" for stem in ("probe", "home__enormous__dark", "home__small__sepia", "__small__dark"))
    )


def test_a_file_that_is_not_a_png_is_never_published_under_a_frame_name(tmp_path: Path) -> None:
    catalogue = ReviewCatalogue(tmp_path, clock=_Clock())
    path = _frame_path(tmp_path, "home--ready__small__dark")
    path.parent.mkdir(parents=True)
    path.write_bytes(b"not an image")
    _modified(path, _NOW - SETTLE_SECONDS - 1)

    catalogue.refresh()
    view = catalogue.run("current")

    assert view is not None
    assert view.frames == ()


def test_a_surface_name_that_contains_the_separator_still_parses() -> None:
    identity = parse_stem("ledger__entry__small__dark")

    assert identity is not None
    assert (identity.surface, identity.viewport, identity.theme) == (
        "ledger__entry",
        ViewportName.SMALL,
        ThemeName.DARK,
    )


def test_frames_are_ordered_by_surface_then_the_viewport_and_theme_vocabularies(tmp_path: Path) -> None:
    catalogue = ReviewCatalogue(tmp_path, clock=_Clock())
    viewports = tuple(ViewportName)
    themes = tuple(ThemeName)
    stems = [
        f"{surface}__{viewport}__{theme}"
        for surface in ("zeta", "alpha")
        for viewport in reversed(viewports)
        for theme in reversed(themes)
    ]
    for index, stem in enumerate(stems):
        _settled_frame(tmp_path, stem, (index, index, index))

    catalogue.refresh()
    view = catalogue.run("current")

    assert view is not None
    expected = [
        f"{surface}__{viewport}__{theme}" for surface in ("alpha", "zeta") for viewport in viewports for theme in themes
    ]
    assert [frame.stem for frame in view.frames] == expected


def test_frames_are_grouped_into_the_elements_they_show_with_each_state_in_order(tmp_path: Path) -> None:
    catalogue = ReviewCatalogue(tmp_path, clock=_Clock())
    stems = (
        "home--stale__small__light",
        "home--ready__large__dark",
        "home--ready__small__dark",
        "seq-modelo-303-first-quarter--workbench__small__dark",
        "seq-modelo-130-first-quarter--workbench__small__dark",
        "seq-modelo-130-first-quarter--sources__small__dark",
        "login__small__dark",
    )
    for index, stem in enumerate(stems):
        _settled_frame(tmp_path, stem, (index, index, index))

    catalogue.refresh()
    view = catalogue.run("current")

    assert view is not None
    assert [(element.key, element.states) for element in view.elements] == [
        ("fixture:home", ("ready", "stale")),
        ("sequence:sources", ("modelo-130-first-quarter",)),
        ("sequence:workbench", ("modelo-130-first-quarter", "modelo-303-first-quarter")),
        ("screen:login", (None,)),
    ]
    home = view.element("fixture:home")
    assert home is not None
    assert [frame.stem for frame in home.frames] == [
        "home--ready__small__dark",
        "home--ready__large__dark",
        "home--stale__small__light",
    ]
    assert view.element("fixture:absent") is None


def test_an_element_digest_moves_when_any_one_of_its_frames_is_re_rendered(tmp_path: Path) -> None:
    catalogue = ReviewCatalogue(tmp_path, clock=_Clock())
    _settled_frame(tmp_path, "home--ready__small__dark", (1, 1, 1))
    _settled_frame(tmp_path, "home--empty__small__dark", (2, 2, 2))
    _settled_frame(tmp_path, "login__small__dark", (3, 3, 3))
    catalogue.refresh()
    before = catalogue.run("current")
    assert before is not None

    rerendered = _frame_path(tmp_path, "home--empty__small__dark")
    _write_png(rerendered, (9, 9, 9))
    _modified(rerendered, _NOW - SETTLE_SECONDS - 0.5)
    catalogue.refresh()
    after = catalogue.run("current")

    assert after is not None
    digests = {element.key: element.digest for element in before.elements}
    assert {element.key: element.digest != digests[element.key] for element in after.elements} == {
        "fixture:home": True,
        "screen:login": False,
    }


def _record(stem: str, digest: str, *, findings: tuple[str, ...]) -> RenderedFrame:
    identity = parse_stem(stem)
    assert identity is not None
    shape = VIEWPORTS[identity.viewport]
    return RenderedFrame(
        surface=identity.surface,
        viewport=identity.viewport,
        columns=shape.columns,
        rows=shape.rows,
        orientation=shape.orientation,
        theme=identity.theme,
        png=f"png/{stem}.png",
        svg=f"svg/{stem}.svg",
        text=f"text/{stem}.txt",
        png_sha256=digest,
        text_sha256="0" * 64,
        cell_height=22,
        geometry_findings=findings,
    )


def test_manifest_readings_attach_only_to_the_pixels_they_were_recorded_against(tmp_path: Path) -> None:
    catalogue = ReviewCatalogue(tmp_path, clock=_Clock())
    described = _settled_frame(tmp_path, "home--ready__small__dark", (1, 1, 1))
    _settled_frame(tmp_path, "home--ready__small__light", (2, 2, 2))
    manifest = Manifest(
        generated_at="2026-09-29T12:00:00+00:00",
        source_revision=_REVISION,
        source_revision_at_end=_REVISION,
        cell_height=22,
        frames=(
            _record("home--ready__small__dark", described, findings=("overflow past the right edge",)),
            _record("home--ready__small__light", "f" * 64, findings=("from an earlier render",)),
        ),
    )
    directory = tmp_path / "current"
    write_manifest(directory, manifest)
    _modified(directory / MANIFEST_NAME, _NOW - SETTLE_SECONDS - 1)

    catalogue.refresh()
    view = catalogue.run("current")

    assert view is not None
    readings = {frame.stem: view.recorded(frame) for frame in view.frames}
    dark = readings["home--ready__small__dark"]
    assert dark is not None
    assert dark.geometry_findings == ("overflow past the right edge",)
    assert readings["home--ready__small__light"] is None


def test_an_unreadable_manifest_is_reported_rather_than_raised(tmp_path: Path) -> None:
    catalogue = ReviewCatalogue(tmp_path, clock=_Clock())
    _settled_frame(tmp_path, "home--ready__small__dark", (1, 1, 1))
    manifest = tmp_path / "current" / MANIFEST_NAME
    manifest.write_text("{", encoding="utf-8")
    _modified(manifest, _NOW - SETTLE_SECONDS - 1)

    catalogue.refresh()
    view = catalogue.run("current")

    assert view is not None
    assert view.manifest is None
    assert view.manifest_error
    assert len(view.frames) == 1


def test_only_scans_the_named_run(tmp_path: Path) -> None:
    catalogue = ReviewCatalogue(tmp_path, only="baseline", clock=_Clock())
    _settled_frame(tmp_path, "home--ready__small__dark", (1, 1, 1), run="current")
    _settled_frame(tmp_path, "home--ready__small__dark", (2, 2, 2), run="baseline")

    catalogue.refresh()

    assert [view.name for view in catalogue.runs()] == ["baseline"]


def test_a_directory_with_no_frames_and_no_manifest_is_not_a_run(tmp_path: Path) -> None:
    (tmp_path / "scratch-output").mkdir()
    catalogue = ReviewCatalogue(tmp_path, clock=_Clock())

    catalogue.refresh()

    assert catalogue.runs() == ()
