"""Real checks on the TUI visual inventory tooling.

Nothing here mocks the harness or fakes an SVG. The rasteriser is proved
against a document the real Textual exporter produced, the inventory against
the real source tree, and the boundary rule against the real package source.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
from PIL import Image

from ..._paths import REPO_ROOT, UTF_8
from .. import _coverage, _diff, _inventory, _raster
from .._artifacts import (
    FailedFrame,
    InterfaceRecord,
    Manifest,
    RenderedFrame,
    SkippedFrame,
    now,
    read_manifest,
    unaccounted_frames,
    write_index,
    write_manifest,
)
from .._artifacts import (
    digest as _artifacts_digest,
)
from .._viewports import DEFAULT_VIEWPORTS, VIEWPORTS, resolve

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_PACKAGE = Path(__file__).resolve().parents[1]


def _tui_importers(root: Path) -> list[str]:
    """Every module under ``root`` that imports the TUI entrypoint package."""
    offenders: list[str] = []
    for module in sorted(root.rglob("*.py")):
        source = module.read_text(encoding=UTF_8)
        for match in re.finditer(r"^\s*(?:from|import)\s+(cadrumo[\w.]*)", source, flags=re.MULTILINE):
            if match.group(1).startswith("cadrumo.entrypoints.tui"):
                offenders.append(f"{module.name}: {match.group(0).strip()}")
    return offenders


def test_no_module_in_this_package_imports_the_tui_entrypoint() -> None:
    """The architecture decision bars a development tool from importing the TUI.

    Checked as text over every module here rather than by importing them: an
    import-time check would only catch a top-level import, and the rule covers
    annotations and deferred imports too. The harness module is allowed to
    NAME the module path, because running it as a subprocess is the one
    external reference the decision sanctions.
    """
    assert _tui_importers(_PACKAGE) == []


def test_the_boundary_check_catches_an_import_that_does_violate_it(tmp_path: Path) -> None:
    """Anti-tautology: a check that never fires proves nothing about the tree.

    A clean scan over the real package is only evidence if the same scan
    reddens on a module that does import the TUI. Proved against a synthetic
    tree so the repository is never mutated to demonstrate it.
    """
    (tmp_path / "innocent.py").write_text("from cadrumo.core import Modelo\n", encoding=UTF_8)
    (tmp_path / "offender.py").write_text(
        "from cadrumo.entrypoints.tui.devtools.surfaces import SURFACES\n",
        encoding=UTF_8,
    )
    (tmp_path / "deferred.py").write_text(
        "def build():\n    import cadrumo.entrypoints.tui.launcher\n",
        encoding=UTF_8,
    )

    caught = _tui_importers(tmp_path)
    assert any(entry.startswith("offender.py") for entry in caught)
    assert any(entry.startswith("deferred.py") for entry in caught), "a function-local import is still an import edge"
    assert not any(entry.startswith("innocent.py") for entry in caught)


def test_the_raster_font_pin_matches_the_readme_renderer_pin() -> None:
    """One font file, one digest, in both dev-lane renderers.

    Read out of the README renderer's SOURCE rather than imported: that module
    builds a filing runtime at import time, and a pin comparison should not
    depend on the application booting.
    """
    source = (REPO_ROOT / "dev" / "readme" / "render_cli_demo.py").read_text(encoding=UTF_8)
    pinned = re.search(r'_FONT_SHA256\s*=\s*"([0-9a-f]{64})"', source)
    assert pinned is not None, "the README renderer no longer pins a font digest"
    assert pinned.group(1) == _raster.FONT_SHA256


def test_the_pinned_font_file_still_carries_the_pinned_digest() -> None:
    """The pin names the committed file, not a file that has since changed."""
    from hashlib import sha256

    assert _raster.FONT_PATH.is_file()
    assert sha256(_raster.FONT_PATH.read_bytes()).hexdigest() == _raster.FONT_SHA256


def test_every_default_viewport_resolves_and_both_orientations_are_covered() -> None:
    """A review matrix with no portrait shape cannot see a portrait defect."""
    resolved = [resolve(name) for name in DEFAULT_VIEWPORTS]
    assert {viewport.orientation for viewport in resolved} == {"landscape", "portrait"}


def test_an_unknown_viewport_refuses_and_names_the_accepted_set() -> None:
    with pytest.raises(KeyError) as refusal:
        resolve("enormous")
    assert "accepted" in str(refusal.value)
    for name in VIEWPORTS:
        assert name in str(refusal.value)


def test_the_inventory_finds_transitively_derived_interfaces() -> None:
    """A class reaching a Textual base through a local base is still an interface.

    ``LoginScreen`` extends ``CredentialScreen``, which extends ``Screen``. A
    scanner that only matched a direct Textual base would silently drop it,
    and the surface an operator logs in through would vanish from the
    inventory.
    """
    found = {interface.name: interface for interface in _inventory.scan()}
    assert "CredentialScreen" in found
    assert found["CredentialScreen"].is_base
    assert found["LoginScreen"].kind == "screen"
    assert "CredentialScreen" in found["LoginScreen"].bases


def test_import_aliases_and_same_named_bases_cannot_escape_the_inventory(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Resolve Python import identity, not an ambiguous bare class spelling."""
    source_root = tmp_path / "src"
    root = source_root / "cadrumo" / "entrypoints" / "tui"
    root.mkdir(parents=True)
    (root / "aliased.py").write_text(
        "from textual.screen import Screen as TuiScreen\nclass AliasedScreen(TuiScreen):\n    pass\n",
        encoding=UTF_8,
    )
    (root / "qualified.py").write_text(
        "import textual.app as textual_app\nclass AliasedApp(textual_app.App):\n    pass\n",
        encoding=UTF_8,
    )
    (root / "first.py").write_text(
        "from textual.screen import Screen as RootScreen\nclass Shared(RootScreen):\n    pass\n",
        encoding=UTF_8,
    )
    (root / "second.py").write_text("class Shared(object):\n    pass\n", encoding=UTF_8)
    (root / "child.py").write_text(
        "from .first import Shared as ImportedShared\nclass ImportedChild(ImportedShared):\n    pass\n",
        encoding=UTF_8,
    )
    monkeypatch.setattr(_inventory, "REPO_ROOT", tmp_path)

    interfaces = _inventory.scan(root)
    found = {interface.name: interface for interface in interfaces}

    assert set(found) == {"AliasedApp", "AliasedScreen", "ImportedChild", "Shared"}
    assert found["AliasedApp"].kind == "app"
    assert found["AliasedScreen"].kind == "screen"
    assert found["ImportedChild"].kind == "screen"
    assert found["Shared"].module.endswith(".first")
    with pytest.raises(_coverage.CoverageError, match="unclassified interface"):
        _coverage.check(interfaces, (), classifications={}, rendered_table={})


def test_the_inventory_excludes_test_trees_and_locates_real_source() -> None:
    for interface in _inventory.scan():
        assert "tests" not in interface.path.parts
        assert interface.path.is_file()
        assert interface.line >= 1


def test_the_coverage_table_only_names_interfaces_that_exist() -> None:
    """A rename must break the table loudly, not quietly drop coverage."""
    known = {interface.qualname for interface in _inventory.scan()}
    mapped = {qualname for qualnames in _coverage.RENDERED_BY.values() for qualname in qualnames}
    assert mapped <= known, f"coverage names interfaces the tree does not define: {sorted(mapped - known)}"
    assert set(_coverage.NOTES) <= known


def test_every_discovered_interface_has_one_stable_explicit_classification() -> None:
    """New interfaces and stale registrations both make the inventory fail."""
    interfaces = _inventory.scan()
    discovered = {interface.qualname for interface in interfaces}
    assert discovered == set(_coverage.CLASSIFICATIONS)
    assert len(interfaces) == 60

    counts = {
        disposition: sum(
            classification.disposition is disposition for classification in _coverage.CLASSIFICATIONS.values()
        )
        for disposition in _coverage.InventoryDisposition
    }
    assert counts == {
        _coverage.InventoryDisposition.COVERED: 5,
        _coverage.InventoryDisposition.FIXTURE_NEEDED: 44,
        _coverage.InventoryDisposition.ABSTRACT_BASE: 9,
        _coverage.InventoryDisposition.DEVELOPMENT_ONLY: 2,
    }


def test_every_concrete_review_surface_has_a_stable_fixture_identity() -> None:
    interfaces = _inventory.scan()
    needed = _coverage.fixture_needed(interfaces)
    assert len(needed) == 44
    for interface in interfaces:
        classification = _coverage.CLASSIFICATIONS[interface.qualname]
        if classification.disposition in {
            _coverage.InventoryDisposition.COVERED,
            _coverage.InventoryDisposition.FIXTURE_NEEDED,
        }:
            assert classification.surface_id is not None
            assert re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", classification.surface_id)
        else:
            assert classification.surface_id is None


def test_every_derived_base_is_explicitly_classified_as_a_base() -> None:
    by_name = {interface.qualname: interface for interface in _inventory.scan()}
    abstract_bases = {
        qualname
        for qualname, classification in _coverage.CLASSIFICATIONS.items()
        if classification.disposition is _coverage.InventoryDisposition.ABSTRACT_BASE
    }
    assert len(abstract_bases) == 9
    assert all(by_name[qualname].is_base for qualname in abstract_bases)


def test_coverage_check_bites_on_unclassified_and_stale_classifications() -> None:
    interfaces = _inventory.scan()
    surfaces = tuple(_coverage.RENDERED_BY)
    missing = dict(_coverage.CLASSIFICATIONS)
    missing.pop(interfaces[0].qualname)
    with pytest.raises(_coverage.CoverageError, match="unclassified interface"):
        _coverage.check(interfaces, surfaces, classifications=missing)

    stale = dict(_coverage.CLASSIFICATIONS)
    stale["cadrumo.entrypoints.tui.removed.StaleScreen"] = _coverage.InterfaceClassification(
        _coverage.InventoryDisposition.FIXTURE_NEEDED,
        "removed-stale",
    )
    with pytest.raises(_coverage.CoverageError, match="stale classification"):
        _coverage.check(interfaces, surfaces, classifications=stale)


def test_coverage_check_refuses_a_surface_the_harness_does_not_offer() -> None:
    interfaces = _inventory.scan()
    with pytest.raises(_coverage.CoverageError) as refusal:
        _coverage.check(interfaces, surfaces=("registration",))
    assert "unknown surface" in str(refusal.value)


def _manifest(frames=(), failures=(), skipped=()) -> Manifest:
    return Manifest(
        generated_at=now(),
        cell_height=22,
        frames=tuple(frames),
        failures=tuple(failures),
        skipped=tuple(skipped),
    )


def _rendered(surface: str, viewport: str, theme: str) -> RenderedFrame:
    return RenderedFrame(
        surface=surface,
        viewport=viewport,
        columns=120,
        rows=40,
        orientation="landscape",
        theme=theme,
        png="a.png",
        svg="a.svg",
        text="a.txt",
        png_sha256="0" * 64,
        text_sha256="0" * 64,
    )


def test_a_run_that_rendered_everything_it_was_asked_for_reports_no_silent_absence() -> None:
    manifest = _manifest(frames=(_rendered("home--ready", "medium", "dark"),))

    assert (
        unaccounted_frames(
            manifest,
            surfaces=("home--ready",),
            viewports=("medium",),
            themes=("dark",),
        )
        == ()
    )


def test_a_refused_or_skipped_frame_still_counts_as_accounted_for() -> None:
    """Refusing loudly is coverage of a kind; vanishing is not."""
    manifest = _manifest(
        failures=(
            FailedFrame(
                surface="home--ready",
                viewport="medium",
                theme="dark",
                kind="REFUSED",
                detail="refused: synthetic",
            ),
        ),
        skipped=(
            SkippedFrame(
                surface="home--ready",
                viewport="medium",
                theme="light",
                reason="surface already refused",
            ),
        ),
    )

    assert (
        unaccounted_frames(
            manifest,
            surfaces=("home--ready",),
            viewports=("medium",),
            themes=("dark", "light"),
        )
        == ()
    )


def test_the_absence_detector_bites_on_a_frame_that_simply_vanished() -> None:
    """The defect this exists for: a requested frame in none of the three lists.

    A manifest that neither rendered a frame nor explained why reads to a
    reviewer exactly like a run that was never asked for it, which is how a
    surface can sit unrendered while the index looks complete.
    """
    manifest = _manifest(frames=(_rendered("home--ready", "medium", "dark"),))

    missing = unaccounted_frames(
        manifest,
        surfaces=("home--ready", "ledger-overview--ready"),
        viewports=("medium",),
        themes=("dark",),
    )

    assert missing == ("ledger-overview--ready/medium/dark",)


def _sample_svg() -> Path:
    """A real Textual export committed nowhere; produced by the harness run."""
    candidates = sorted((REPO_ROOT / ".tmp-tui-visual-inventory").rglob("svg/*.svg"))
    if not candidates:
        pytest.skip("no rendered SVG available; run `python -m dev.tui render` first")
    return candidates[0]


def test_rasterising_a_real_export_produces_the_declared_cell_grid(tmp_path: Path) -> None:
    """The PNG's pixel size is the terminal grid times the cell size.

    This is the property that makes the artefact reviewable at a stated
    resolution: an image whose height is not a whole number of rows means the
    row mapping drifted, and glyphs are landing between cells.
    """
    svg = _sample_svg()
    destination = tmp_path / "frame.png"
    result = _raster.rasterise(svg, destination, cell_height=20)

    assert result.path == destination
    width, height = Image.open(destination).size

    # The SVG states its own terminal extent; the PNG must be exactly that
    # many rows tall, so a drifted row mapping cannot pass by rounding.
    markup = svg.read_text(encoding=UTF_8)
    terminal = _raster._TERMINAL_CLIP.search(markup)
    assert terminal is not None
    cell_width_units, cell_height_units = _raster._cell_size(markup)
    expected_rows = round(float(terminal["height"]) / cell_height_units)
    expected_columns = round(float(terminal["width"]) / cell_width_units)

    assert height == expected_rows * 20
    assert width == expected_columns * (width // expected_columns)


def test_raising_the_cell_height_raises_the_resolution_proportionally(tmp_path: Path) -> None:
    """The same frame at a larger cell is the same grid, more pixels."""
    svg = _sample_svg()
    small = Image.open(_raster.rasterise(svg, tmp_path / "small.png", cell_height=14).path).size
    large = Image.open(_raster.rasterise(svg, tmp_path / "large.png", cell_height=28).path).size
    assert large[1] == small[1] * 2
    assert large[0] > small[0]


def test_rasterising_a_document_that_is_not_a_terminal_refuses(tmp_path: Path) -> None:
    """A non-terminal SVG must refuse rather than write a plausible blank."""
    stray = tmp_path / "stray.svg"
    stray.write_text('<svg viewBox="0 0 10 10"><rect x="0" y="0" width="10" height="10"/></svg>', encoding=UTF_8)
    with pytest.raises(_raster.RasterError):
        _raster.rasterise(stray, tmp_path / "out.png")


def _frame(key: str, *, png_digest: str, text_digest: str) -> RenderedFrame:
    surface, viewport, theme = key.split("/")
    return RenderedFrame(
        surface=surface,
        viewport=viewport,
        columns=80,
        rows=24,
        orientation="landscape",
        theme=theme,
        png=f"png/{surface}.png",
        svg=f"svg/{surface}.svg",
        text=f"text/{surface}.txt",
        png_sha256=png_digest,
        text_sha256=text_digest,
    )


def _run(tmp_path: Path, name: str, frames: tuple[RenderedFrame, ...], body: str) -> Path:
    directory = tmp_path / name
    for frame in frames:
        target = directory / frame.text
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(body, encoding=UTF_8)
    write_manifest(directory, Manifest(generated_at="2026-01-01T00:00:00+00:00", cell_height=22, frames=frames))
    return directory


def test_a_diff_of_a_run_against_itself_reports_no_change(tmp_path: Path) -> None:
    frames = (_frame("status/small/dark", png_digest="a" * 64, text_digest="b" * 64),)
    directory = _run(tmp_path, "one", frames, "same\n")
    manifest = read_manifest(directory)
    diffs = _diff.compare(directory, manifest, directory, manifest)
    assert [entry.change for entry in diffs] == [_diff.Change.UNCHANGED]
    assert "no change" in _diff.render_report(diffs)


def test_a_diff_separates_pixel_change_from_text_change(tmp_path: Path) -> None:
    """The two axes are reported independently, because they mean different things."""
    before = (_frame("status/small/dark", png_digest="a" * 64, text_digest="b" * 64),)
    after = (_frame("status/small/dark", png_digest="c" * 64, text_digest="b" * 64),)
    baseline = _run(tmp_path, "before", before, "same\n")
    candidate = _run(tmp_path, "after", after, "same\n")

    diffs = _diff.compare(baseline, read_manifest(baseline), candidate, read_manifest(candidate))
    assert diffs[0].change is _diff.Change.CHANGED
    assert diffs[0].pixels_differ
    assert not diffs[0].text_differ
    assert diffs[0].text_diff == ""


def test_a_text_change_carries_a_readable_unified_diff(tmp_path: Path) -> None:
    before = (_frame("status/small/dark", png_digest="a" * 64, text_digest="b" * 64),)
    after = (_frame("status/small/dark", png_digest="a" * 64, text_digest="d" * 64),)
    baseline = _run(tmp_path, "before", before, "Estado\nAvisos\n")
    candidate = _run(tmp_path, "after", after, "Estado\nAlertas\n")

    diffs = _diff.compare(baseline, read_manifest(baseline), candidate, read_manifest(candidate))
    assert diffs[0].text_differ
    assert "-Avisos" in diffs[0].text_diff
    assert "+Alertas" in diffs[0].text_diff


def test_a_diff_names_added_and_removed_frames(tmp_path: Path) -> None:
    baseline = _run(
        tmp_path,
        "before",
        (_frame("status/small/dark", png_digest="a" * 64, text_digest="b" * 64),),
        "x\n",
    )
    candidate = _run(
        tmp_path,
        "after",
        (_frame("login/small/dark", png_digest="a" * 64, text_digest="b" * 64),),
        "x\n",
    )
    diffs = _diff.compare(baseline, read_manifest(baseline), candidate, read_manifest(candidate))
    changes = {entry.key: entry.change for entry in diffs}
    assert changes["status/small/dark"] is _diff.Change.REMOVED
    assert changes["login/small/dark"] is _diff.Change.ADDED


def test_a_highlight_refuses_to_compare_frames_of_different_shapes(tmp_path: Path) -> None:
    """A resize is not a visual difference, and must not be drawn as one."""
    small, large = tmp_path / "small.png", tmp_path / "large.png"
    Image.new("RGB", (100, 100), "#000000").save(small)
    Image.new("RGB", (200, 100), "#000000").save(large)
    assert _diff.write_highlight(small, large, tmp_path / "out.png") is None


def test_a_highlight_of_two_same_shaped_frames_is_written(tmp_path: Path) -> None:
    before, after = tmp_path / "a.png", tmp_path / "b.png"
    Image.new("RGB", (60, 40), "#000000").save(before)
    changed = Image.new("RGB", (60, 40), "#000000")
    changed.putpixel((10, 10), (255, 0, 0))
    changed.save(after)

    written = _diff.write_highlight(before, after, tmp_path / "out.png")
    assert written is not None
    assert Image.open(written).size[0] > 60 * 2


def test_a_manifest_roundtrips_through_disk_with_every_field_populated(tmp_path: Path) -> None:
    """Strict equality across the real write and read, no field left default."""
    frame = RenderedFrame(
        surface="status",
        viewport="tall",
        columns=80,
        rows=50,
        orientation="portrait",
        theme="light",
        png="png/status.png",
        svg="svg/status.svg",
        text="text/status.txt",
        png_sha256="a" * 64,
        text_sha256="b" * 64,
        elapsed_ms=1234.5,
        geometry_findings=("ContentScroll overflows but cannot scroll",),
        missing_glyphs=("ⓘ",),
    )
    manifest = Manifest(
        schema_version=2,
        generated_at="2026-01-01T00:00:00+00:00",
        cell_height=26,
        frames=(frame,),
        interfaces=(
            InterfaceRecord(
                qualname="pkg.Painted",
                kind="app",
                locator="a.py:1",
                rendered_by=("status",),
                note="a stated reading",
            ),
        ),
        failures=(
            FailedFrame(
                surface="modelo-work-wizard",
                viewport="small",
                theme="dark",
                kind="refused",
                attempts=3,
                detail="refused: application.modelo.errors.profile_readiness_setup_incomplete",
            ),
        ),
        skipped=(
            SkippedFrame(
                surface="modelo-work-wizard",
                viewport="medium",
                theme="light",
                reason="surface already refused: readiness incomplete",
            ),
        ),
    )
    write_manifest(tmp_path, manifest)
    assert read_manifest(tmp_path) == manifest


def test_a_manifest_missing_a_field_refuses_at_load(tmp_path: Path) -> None:
    """Anti-tautology: corrupt the payload, prove the read path notices."""
    import json

    from pydantic import ValidationError

    manifest = Manifest(generated_at="2026-01-01T00:00:00+00:00", cell_height=22)
    path = write_manifest(tmp_path, manifest)
    payload = json.loads(path.read_text(encoding=UTF_8))
    del payload["cell_height"]
    path.write_text(json.dumps(payload), encoding=UTF_8)

    with pytest.raises(ValidationError):
        read_manifest(tmp_path)


def test_the_index_reports_uncovered_interfaces_rather_than_omitting_them(tmp_path: Path) -> None:
    """A report that lists only what rendered reads as full coverage."""
    manifest = Manifest(
        generated_at="2026-01-01T00:00:00+00:00",
        cell_height=22,
        interfaces=(
            InterfaceRecord(qualname="pkg.Painted", kind="app", locator="a.py:1", rendered_by=("status",)),
            InterfaceRecord(qualname="pkg.Unpainted", kind="screen", locator="b.py:2"),
        ),
    )
    body = write_index(tmp_path, manifest).read_text(encoding=UTF_8)
    assert "pkg.Unpainted" in body
    assert "NOT RENDERED" in body
    assert len(manifest.uncovered) == 1


def test_the_frame_reading_redacts_the_harness_build_timing_only() -> None:
    """A timing wobble must not read as a visual change; real content must.

    Without this, every frame differs between any two runs and the diff
    reports the whole matrix as changed, which is indistinguishable from
    reporting nothing.
    """
    from .._harness import Capture
    from .._viewports import resolve as resolve_viewport

    header = "──────── frame 0 ──────── status · 80x24 · dark · auto · 591ms ────────"
    body = "│ Límite absoluto de la sesión 2026-08-26T21:23+00:00 │"
    slower = Capture(
        surface="status",
        viewport=resolve_viewport("small"),
        theme="dark",
        svg_path=Path("unused.svg"),
        frame_text=f"{header}\n{body}",
    )
    faster = Capture(
        surface="status",
        viewport=resolve_viewport("small"),
        theme="dark",
        svg_path=Path("unused.svg"),
        frame_text=f"{header.replace('591ms', '2176ms')}\n{body}",
    )

    assert slower.elapsed_ms == 591.0
    assert faster.elapsed_ms == 2176.0
    assert slower.stable_text == faster.stable_text, "timing alone must not change the diffed text"
    assert "591ms" not in slower.stable_text
    assert body in slower.stable_text, "surface content must survive redaction untouched"


def test_a_glyph_the_pinned_font_lacks_is_detected_as_missing() -> None:
    """Missing-glyph detection must fire on a real tofu, not on ink presence.

    U+24D8 (circled i) is absent from the pinned Cascadia Mono and appears on
    the real status page's notice band. A detector keyed on an empty bitmap
    reports it as present, because ``.notdef`` is a drawn box with ink -- so
    this asserts both directions against characters the font really does and
    really does not carry.
    """
    pixels = 20
    font = _raster._font(pixels)

    assert _raster._is_missing(font, pixels, "\u24d8"), "the circled-i tofu must be reported"
    assert not _raster._is_missing(font, pixels, "A")
    assert not _raster._is_missing(font, pixels, "\u2502"), "box drawing must not read as missing"
    assert not _raster._is_missing(font, pixels, "ñ"), "accented Spanish text must not read as missing"


def test_rasterising_the_status_page_reports_its_untranslatable_glyph(tmp_path: Path) -> None:
    """End to end: a frame containing the tofu names it in the result."""
    candidates = sorted((REPO_ROOT / ".tmp-tui-visual-inventory").rglob("svg/status__*.svg"))
    if not candidates:
        pytest.skip("no rendered status SVG available")
    for svg in candidates:
        if "\u24d8" in svg.read_text(encoding=UTF_8):
            result = _raster.rasterise(svg, tmp_path / "status.png")
            assert "\u24d8" in result.missing_glyphs
            return
    pytest.skip("no rendered status frame carried the notice glyph")


def test_a_harness_refusal_is_told_apart_from_a_harness_crash() -> None:
    """The two failure kinds drive different handling, so the read must be exact.

    Both shapes are the real ones this tool has seen: the wizard's readiness
    refusal, and the import error a peer's half-finished edit produced in a
    shared worktree.
    """
    from .._harness import FailureKind, classify

    refusal = (
        "harness `open modelo-work-wizard --size 120x40 --theme dark` exited 1\n"
        "refused: application.modelo.errors.profile_readiness_setup_incomplete\n"
        "the surface did not open; the session on disk is unchanged."
    )
    crash = (
        "harness `open form --size 80x50 --theme dark` exited 1\n"
        "Traceback (most recent call last):\n"
        '  File "<frozen runpy>", line 198, in _run_module_as_main\n'
        "NameError: name 'InventorySelector' is not defined."
    )

    assert classify(refusal) is FailureKind.REFUSED
    assert classify(crash) is FailureKind.CRASHED
    assert classify("") is FailureKind.CRASHED, "an unreadable failure must not be mistaken for a considered refusal"


def test_a_refusal_that_follows_a_traceback_still_reads_as_a_crash() -> None:
    """Order decides: whichever marker the harness printed first is the cause.

    A traceback that happens to contain the word ``refused:`` further down
    must not be downgraded into a deterministic refusal, because downgrading
    it would skip the whole surface on the strength of a transient crash.
    """
    from .._harness import FailureKind, classify

    output = "Traceback (most recent call last):\n  ...\nValueError: refused: something that looks like a refusal"
    assert classify(output) is FailureKind.CRASHED


def test_a_harness_error_defaults_to_the_retryable_kind() -> None:
    """An unclassified failure must not silently condemn a whole surface."""
    from .._harness import FailureKind, HarnessError

    assert HarnessError("boom").kind is FailureKind.CRASHED


def test_the_refusal_reason_is_extracted_for_the_skip_note() -> None:
    """A skipped frame must name why, in the harness's own words."""
    from ..cli import _first_refusal_line

    detail = (
        "harness `open modelo-work-wizard --size 120x40 --theme dark` exited 1\n"
        "refused: application.modelo.errors.profile_readiness_setup_incomplete\n"
        "the surface did not open; the session on disk is unchanged."
    )
    assert _first_refusal_line(detail) == "application.modelo.errors.profile_readiness_setup_incomplete"
    assert _first_refusal_line("") == "no diagnostics"


def test_a_blocked_surface_is_named_from_failures_and_skips_together() -> None:
    """A surface is blocked when it produced no frame, however it got there.

    The wizard's real shape: one recorded refusal plus the rest of its matrix
    recorded as skipped. Counting only failures would under-report it, and
    counting only skips would miss the first frame that actually tried.
    """
    manifest = Manifest(
        generated_at="2026-01-01T00:00:00+00:00",
        cell_height=22,
        frames=(
            RenderedFrame(
                surface="status",
                viewport="small",
                columns=80,
                rows=24,
                orientation="landscape",
                theme="dark",
                png="p",
                svg="s",
                text="t",
                png_sha256="a" * 64,
                text_sha256="b" * 64,
            ),
        ),
        failures=(
            FailedFrame(
                surface="modelo-work-wizard",
                viewport="small",
                theme="dark",
                kind="refused",
                detail="refused: readiness incomplete",
            ),
        ),
        skipped=(
            SkippedFrame(
                surface="modelo-work-wizard",
                viewport="tall",
                theme="light",
                reason="surface already refused: readiness incomplete",
            ),
        ),
    )
    assert manifest.blocked_surfaces == ("modelo-work-wizard",)
    assert "status" not in manifest.blocked_surfaces


def test_the_index_reports_blocked_surfaces_and_unattempted_frames(tmp_path: Path) -> None:
    """A run that stops mentioning what it gave up on reads as full coverage."""
    manifest = Manifest(
        generated_at="2026-01-01T00:00:00+00:00",
        cell_height=22,
        failures=(
            FailedFrame(
                surface="modelo-work-wizard",
                viewport="small",
                theme="dark",
                kind="refused",
                attempts=1,
                detail="refused: readiness incomplete",
            ),
        ),
        skipped=(
            SkippedFrame(
                surface="modelo-work-wizard",
                viewport="tall",
                theme="light",
                reason="surface already refused: readiness incomplete",
            ),
        ),
    )
    body = write_index(tmp_path, manifest).read_text(encoding=UTF_8)
    assert "Surfaces that produced no frame" in body
    assert "Not attempted" in body
    assert "modelo-work-wizard/tall/light" in body
    assert "readiness incomplete" in body


def test_a_manifest_from_an_older_schema_is_refused_not_upgraded(tmp_path: Path) -> None:
    """Review runs are disposable, so a stale one is re-rendered, never migrated.

    The refusal must name both versions and say what to do; a bare validation
    error tells the operator nothing about which of the two to fix.
    """
    import json

    from .._artifacts import MANIFEST_SCHEMA_VERSION, ManifestVersionError

    stale = {
        "schema_version": MANIFEST_SCHEMA_VERSION - 1,
        "generated_at": "2026-01-01T00:00:00+00:00",
        "cell_height": 22,
        "failures": ["form: harness refused"],
    }
    (tmp_path / "manifest.json").write_text(json.dumps(stale), encoding=UTF_8)

    with pytest.raises(ManifestVersionError) as refusal:
        read_manifest(tmp_path)
    message = str(refusal.value)
    assert str(MANIFEST_SCHEMA_VERSION) in message
    assert "render" in message, "the refusal must say how to recover"


def test_a_manifest_with_no_schema_version_is_refused(tmp_path: Path) -> None:
    """An absent version is unknown provenance, not an implicit current one."""
    import json

    from .._artifacts import ManifestVersionError

    (tmp_path / "manifest.json").write_text(json.dumps({"generated_at": "x", "cell_height": 22}), encoding=UTF_8)
    with pytest.raises(ManifestVersionError):
        read_manifest(tmp_path)


def test_repainting_a_run_rewrites_only_the_raster_derived_fields(tmp_path: Path) -> None:
    """A repaint must not invent capture data it did not observe.

    The PNG digest and the missing-glyph set belong to the rasteriser and are
    rewritten; the captured text, the timing and the geometry readings belong
    to the harness run that produced them and must survive untouched.
    """
    svg = _sample_svg()
    run = tmp_path / "run"
    (run / "svg").mkdir(parents=True)
    (run / "text").mkdir(parents=True)
    (run / "svg" / "frame.svg").write_bytes(svg.read_bytes())
    (run / "text" / "frame.txt").write_text("captured\n", encoding=UTF_8)

    original = RenderedFrame(
        surface="status",
        viewport="small",
        columns=80,
        rows=24,
        orientation="landscape",
        theme="dark",
        png="png/frame.png",
        svg="svg/frame.svg",
        text="text/frame.txt",
        png_sha256="0" * 64,
        text_sha256="1" * 64,
        elapsed_ms=987.0,
        geometry_findings=("something the harness measured",),
    )
    write_manifest(run, Manifest(generated_at="2026-01-01T00:00:00+00:00", cell_height=22, frames=(original,)))

    result = _raster.rasterise(run / original.svg, run / original.png, cell_height=18)
    repainted = original.model_copy(
        update={"png_sha256": _artifacts_digest(run / original.png), "missing_glyphs": result.missing_glyphs},
    )

    assert repainted.png_sha256 != original.png_sha256, "the repaint must actually change the image digest"
    assert repainted.elapsed_ms == original.elapsed_ms
    assert repainted.geometry_findings == original.geometry_findings
    assert repainted.text_sha256 == original.text_sha256


def test_render_has_no_free_form_run_target() -> None:
    """The review path is a contract, not a per-invocation choice.

    `render` must not accept a run name. Nine ad-hoc directories once sat side
    by side because every session invented one, and the reviewer could never be
    told a stable path. A named run is now only reachable through `snapshot`,
    which can copy a review that happened but cannot aim a render elsewhere.
    """
    import inspect

    from ..cli import render_command, snapshot_command

    assert "run" not in inspect.signature(render_command).parameters
    assert "name" in inspect.signature(snapshot_command).parameters


def test_the_canonical_review_directory_is_stable_and_singular() -> None:
    """One default name, and runs live nowhere but under `runs/`."""
    from .._artifacts import DEFAULT_RUN_NAME, RUN_ROOT, RUNS_DIR, SCRATCH_DIR, run_directory

    assert DEFAULT_RUN_NAME == "current"
    assert run_directory(DEFAULT_RUN_NAME) == RUNS_DIR / "current"
    assert RUNS_DIR.parent == RUN_ROOT
    assert SCRATCH_DIR.parent == RUN_ROOT
    assert RUNS_DIR != SCRATCH_DIR, "probe output must not share the review tree"


def test_snapshot_refuses_to_overwrite_the_canonical_review() -> None:
    """`snapshot current` would make the contract path a copy of itself."""
    import typer

    from ..cli import snapshot_command

    with pytest.raises(typer.Exit) as refusal:
        snapshot_command(name="current")
    assert refusal.value.exit_code == 1


def test_every_declared_background_band_is_actually_painted(tmp_path: Path) -> None:
    """No cell a band covers may fall through to the page colour.

    This is the bug the whole review instrument turned on. Columns were mapped
    with ``int(x // cell_width)``, and 536.8 / 12.2 is 43.99999999999999 in
    IEEE floating point -- so a band landed one column left, left the column it
    should have covered unpainted, and that bare cell showed the page colour
    through as a stray block: pale on the light appearance, dark on the dark
    one. Buttons appeared to have holes punched in them.

    Asserting on the RENDERED PIXELS rather than on the mapping arithmetic,
    because the arithmetic is exactly what was wrong and a test written in its
    own terms would have agreed with it.
    """
    import html

    svg = _sample_svg()
    destination = tmp_path / "frame.png"
    cell_height = 20
    _raster.rasterise(svg, destination, cell_height=cell_height)

    markup = svg.read_text(encoding=UTF_8)
    cell_width_units, cell_height_units = _raster._cell_size(markup)
    image = Image.open(destination).convert("RGB")
    terminal = _raster._TERMINAL_CLIP.search(markup)
    assert terminal is not None
    cell_width = image.width // round(float(terminal["width"]) / cell_width_units)

    def expected(colour: str) -> tuple[int, int, int]:
        raw = colour.lstrip("#")
        return (int(raw[0:2], 16), int(raw[2:4], 16), int(raw[4:6], 16))

    # Cells carrying a glyph are excluded: the glyph's own ink legitimately
    # differs from the band colour underneath it.
    inked: set[tuple[int, int]] = set()
    for run in _raster._TEXT_RUN.finditer(markup):
        row = int(float(run["y"]) // cell_height_units)
        start = round(float(run["x"]) / cell_width_units)
        for index, character in enumerate(html.unescape(run["content"])):
            if character.strip():
                inked.add((row, start + index))

    holes: list[str] = []
    for band in _raster._CELL_RECT.finditer(markup):
        row = int(float(band["y"]) // cell_height_units)
        start = round(float(band["x"]) / cell_width_units)
        span = max(round(float(band["width"]) / cell_width_units), 1)
        for column in range(start, start + span):
            if (row, column) in inked:
                continue
            x = column * cell_width + cell_width // 2
            y = row * cell_height + cell_height // 2
            if not (0 <= x < image.width and 0 <= y < image.height):
                continue
            if image.getpixel((x, y)) != expected(band["colour"]):
                holes.append(f"row {row} col {column}: expected {band['colour']}, got {image.getpixel((x, y))}")

    assert holes == [], "background bands not painted (stray blocks):\n" + "\n".join(holes[:12])


def test_column_mapping_survives_floating_point_cell_origins() -> None:
    """The exact arithmetic trap, pinned so it cannot come back.

    Every value here is a real cell origin taken from a Textual export.
    """
    cell = 12.2
    for origin, column in ((536.8, 44), (719.8, 59), (561.2, 46), (707.6, 58), (0.0, 0)):
        assert round(origin / cell) == column, f"{origin} should map to column {column}"
    assert int(536.8 // cell) == 43, "the floored form is wrong here; that is why rounding is used"
