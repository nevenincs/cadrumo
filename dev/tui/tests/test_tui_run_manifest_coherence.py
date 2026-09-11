"""Coherence between a run's manifest and the directory it describes.

A run is a manifest and the files it names, and the two can disagree in both
directions. The sweep walks the directory and reports what the manifest fails
to claim; :func:`missing_artifacts` walks the manifest and reports what the
directory fails to hold. Only the first direction was ever walked, which is
why a claim that outlived its file surfaced as a `FileNotFoundError` inside
the diff rather than as a statement about the run.

Split out of ``test_tui_visual_inventory`` when that module passed the
per-module size budget; the inventory, raster and coverage checks stay there.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from PIL import Image

from dev._paths import UTF_8

from .._artifacts import (
    Manifest,
    ManifestVersionError,
    RenderedFrame,
    digest,
    missing_artifacts,
    purge_stale_artifacts,
    read_manifest,
    source_fingerprint,
    stale_artifacts,
    write_index,
    write_manifest,
)
from .._viewports import resolve as resolve_viewport

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_REVISION = "a" * 64
"""A settled source fingerprint: both ends of a coherent run report it."""


def _manifest(frames: tuple[RenderedFrame, ...] = ()) -> Manifest:
    return Manifest(
        source_revision=_REVISION,
        source_revision_at_end=_REVISION,
        generated_at="2026-01-01T00:00:00+00:00",
        cell_height=22,
        frames=frames,
    )


def _rendered(surface: str, viewport: str, theme: str) -> RenderedFrame:
    shape = resolve_viewport(viewport)
    return RenderedFrame(
        surface=surface,
        viewport=shape.name,
        columns=shape.columns,
        rows=shape.rows,
        orientation=shape.orientation,
        theme=theme,
        png="png/a.png",
        svg="svg/a.svg",
        text="text/a.txt",
        png_sha256="0" * 64,
        text_sha256="0" * 64,
        cell_height=22,
    )


def test_a_run_directory_reports_the_frames_its_manifest_does_not_claim(tmp_path: Path) -> None:
    """A frame from an earlier render is indistinguishable from a current one.

    The manifest is right in both directions; the DIRECTORY is what misleads a
    reviewer who opens it, which is how a surface gets signed off as it looked
    two code changes ago.
    """
    for kind in ("png", "svg", "text"):
        (tmp_path / kind).mkdir()
    (tmp_path / "png" / "a.png").write_bytes(b"")
    (tmp_path / "svg" / "a.svg").write_text("", encoding="utf-8")
    (tmp_path / "text" / "a.txt").write_text("", encoding="utf-8")
    (tmp_path / "png" / "left-behind.png").write_bytes(b"")

    manifest = _manifest(frames=(_rendered("home--ready", "medium", "dark"),))
    stale = stale_artifacts(tmp_path, manifest)

    assert [path.name for path in stale] == ["left-behind.png"]


def test_purging_removes_only_the_unclaimed_frames(tmp_path: Path) -> None:
    """The claimed frames, the manifest and the index all survive a purge."""
    for kind in ("png", "svg", "text"):
        (tmp_path / kind).mkdir()
    (tmp_path / "png" / "a.png").write_bytes(b"")
    (tmp_path / "svg" / "a.svg").write_text("", encoding="utf-8")
    (tmp_path / "text" / "a.txt").write_text("", encoding="utf-8")
    (tmp_path / "png" / "left-behind.png").write_bytes(b"")
    (tmp_path / "manifest.json").write_text("{}", encoding="utf-8")

    manifest = _manifest(frames=(_rendered("home--ready", "medium", "dark"),))
    removed = purge_stale_artifacts(tmp_path, manifest)

    assert [path.name for path in removed] == ["left-behind.png"]
    assert (tmp_path / "png" / "a.png").is_file()
    assert (tmp_path / "svg" / "a.svg").is_file()
    assert (tmp_path / "text" / "a.txt").is_file()
    assert (tmp_path / "manifest.json").is_file()
    assert stale_artifacts(tmp_path, manifest) == ()


def test_a_manifest_whose_run_spanned_a_source_change_says_so() -> None:
    """A run that straddles an edit must announce it, not average it.

    The full matrix takes about twenty-five minutes and renders each surface in
    its own subprocess, so code landing mid-run splits the output: early frames
    show the old behaviour, late frames the new. A manifest carrying only
    `generated_at` claims all of them equally, which is worse than serving
    stale frames from an earlier run -- those announce themselves as another
    run, while these are all reported as current. It happened: a matrix spanned
    the table-width work and produced 174 frames in which some tables were
    clipped and some were not.
    """
    coherent = Manifest(
        source_revision=_REVISION,
        source_revision_at_end=_REVISION,
        generated_at="2026-01-01T00:00:00+00:00",
        cell_height=22,
    )
    assert not coherent.spans_a_source_change

    split = Manifest(
        source_revision=_REVISION,
        source_revision_at_end="b" * 64,
        generated_at="2026-01-01T00:00:00+00:00",
        cell_height=22,
    )
    assert split.spans_a_source_change, (
        "a run whose source changed between its first and last frame reports as coherent"
    )


def test_the_source_fingerprint_follows_the_code_that_renders_the_frames(tmp_path: Path) -> None:
    """The fingerprint must move when the rendered source moves, and only then.

    Content-based rather than a git revision on purpose: a render is normally
    started from a DIRTY worktree, where `git rev-parse HEAD` is identical
    before and after an edit and therefore blind to exactly the change this
    guards against.

    Exercised against a temporary tree rather than the real package. An earlier
    draft edited `home.py` and restored it in a `finally`, which works right up
    until the worktree this repository is edited in -- shared, and swept by a
    concurrent writer -- is committed during the second the file is modified.
    """
    (tmp_path / "nested").mkdir()
    (tmp_path / "a.py").write_text("x = 1\n", encoding="utf-8")
    (tmp_path / "nested" / "b.py").write_text("y = 2\n", encoding="utf-8")
    before = source_fingerprint(tmp_path)

    assert source_fingerprint(tmp_path) == before, "the fingerprint is not stable across calls"

    (tmp_path / "nested" / "b.py").write_text("y = 3\n", encoding="utf-8")
    assert source_fingerprint(tmp_path) != before, "editing a nested module did not move the fingerprint"

    (tmp_path / "nested" / "b.py").write_text("y = 2\n", encoding="utf-8")
    assert source_fingerprint(tmp_path) == before, "the fingerprint did not return when the edit was reverted"

    (tmp_path / "c.txt").write_text("not python\n", encoding="utf-8")
    assert source_fingerprint(tmp_path) == before, "a non-source file moved the fingerprint"


def _painted_png(target: Path, *, rows: int, columns: int, cell_height: int) -> None:
    """Write a PNG whose pixel size is a real terminal grid at that cell height."""
    target.parent.mkdir(parents=True, exist_ok=True)
    width = max(columns * (cell_height // 2), 1)
    Image.new("RGB", (width, rows * cell_height), (0, 0, 0)).save(target)


def test_a_partly_repainted_run_records_the_height_each_frame_is_actually_at(tmp_path: Path) -> None:
    """A repaint that reaches only some frames must not be recorded as reaching all.

    `rasterise` keeps any frame whose SVG has gone missing exactly as it
    was, then stamps the requested cell height onto the manifest. While the
    height lived only at run level that stamp covered the kept frames too,
    so the record asserted a resolution their pixels were never repainted
    to. No ordering fixes it: the run genuinely produces frames at two
    heights, and one scalar cannot say two things.

    Both readings are exercised here against the same run. The retired one
    is the run-level scalar applied to every frame; it contradicts the
    bytes on disk. The current one is each frame's own record; it matches.
    """
    kept = RenderedFrame(
        surface="status",
        viewport="small",
        columns=80,
        rows=24,
        orientation="landscape",
        theme="dark",
        png="png/kept.png",
        svg="svg/kept.svg",
        text="text/kept.txt",
        png_sha256="0" * 64,
        text_sha256="1" * 64,
        cell_height=22,
    )
    repainted = kept.model_copy(update={"surface": "ledger", "png": "png/ledger.png", "cell_height": 14})

    _painted_png(tmp_path / kept.png, rows=kept.rows, columns=kept.columns, cell_height=22)
    _painted_png(
        tmp_path / repainted.png,
        rows=repainted.rows,
        columns=repainted.columns,
        cell_height=14,
    )

    manifest = Manifest(
        source_revision=_REVISION,
        source_revision_at_end=_REVISION,
        generated_at="2026-01-01T00:00:00+00:00",
        cell_height=14,
        frames=(kept, repainted),
    )
    write_manifest(tmp_path, manifest)
    reloaded = read_manifest(tmp_path)

    # The disagreement survives the real write and read, and is named.
    assert reloaded.frames_at_a_foreign_cell_height == (kept.key,)

    for frame in reloaded.frames:
        measured = Image.open(tmp_path / frame.png).height // frame.rows
        assert measured == frame.cell_height, (
            f"{frame.key}: the frame records {frame.cell_height}px but its PNG is at {measured}px"
        )

    # The retired reading, on the same run, interrupted at the same point:
    # one number for every frame. It is false about the frame that was kept.
    retired = Image.open(tmp_path / kept.png).height // kept.rows
    assert retired != reloaded.cell_height, (
        f"the retired run-level reading would have claimed {reloaded.cell_height}px for pixels that are at {retired}px"
    )

    # A reviewer reading the index is told, rather than shown one number.
    index = write_index(tmp_path, reloaded).read_text(encoding=UTF_8)
    assert "14px requested" in index
    assert "22px" in index
    assert "1 frame(s) not at the requested height" in index


def test_a_coherent_run_still_reports_one_cell_height(tmp_path: Path) -> None:
    """The normal path: every frame at the requested height, banner unchanged in shape."""
    frame = RenderedFrame(
        surface="status",
        viewport="small",
        columns=80,
        rows=24,
        orientation="landscape",
        theme="dark",
        png="png/status.png",
        svg="svg/status.svg",
        text="text/status.txt",
        png_sha256="0" * 64,
        text_sha256="1" * 64,
        cell_height=22,
    )
    manifest = Manifest(
        source_revision=_REVISION,
        source_revision_at_end=_REVISION,
        generated_at="2026-01-01T00:00:00+00:00",
        cell_height=22,
        frames=(frame,),
    )

    assert manifest.frames_at_a_foreign_cell_height == ()
    index = write_index(tmp_path, manifest).read_text(encoding=UTF_8)
    assert "cell height 22px" in index
    assert "requested" not in index


def _run_directory_holding(tmp_path: Path, frame: RenderedFrame) -> Path:
    """Write the three files a frame record names, so the run is coherent."""
    for name in (frame.png, frame.svg, frame.text):
        target = tmp_path / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(b"")
    return tmp_path


def test_a_coherent_run_names_nothing_the_directory_does_not_hold(tmp_path: Path) -> None:
    """The normal path, asserted first so the refusal below is not vacuous.

    Every gate here would pass on an empty walk, and an empty walk is exactly
    what a mistyped subdirectory or a renamed field produces.
    """
    frame = _rendered("home--ready", "medium", "dark")
    _run_directory_holding(tmp_path, frame)
    manifest = _manifest(frames=(frame,))

    assert missing_artifacts(tmp_path, manifest) == ()
    assert stale_artifacts(tmp_path, manifest) == ()


def test_a_claim_whose_file_was_removed_is_reported_by_name(tmp_path: Path) -> None:
    """The direction nothing walked: a record that outlived its bytes.

    Reproduced the way it actually happens rather than by deleting all three
    files: one half of a pair goes and the other stays, so the run still looks
    whole from the manifest and clean from the sweep.
    """
    frame = _rendered("home--ready", "medium", "dark")
    _run_directory_holding(tmp_path, frame)
    manifest = _manifest(frames=(frame,))
    (tmp_path / frame.svg).unlink()

    assert missing_artifacts(tmp_path, manifest) == (frame.svg,)
    assert stale_artifacts(tmp_path, manifest) == (), (
        "the sweep reports the same run as clean, which is why the loss was invisible"
    )


def test_the_purge_can_leave_a_claim_without_its_file(tmp_path: Path) -> None:
    """The reachable path, driven through production code rather than asserted.

    `purge_stale_artifacts` re-checks `exists()` before every unlink so a frame
    that goes away mid-sweep does not take the run down. That is the right call
    and it is also how a claim survives its file: the removal is tolerated and
    nothing revisits the manifest afterwards.
    """
    frame = _rendered("home--ready", "medium", "dark")
    _run_directory_holding(tmp_path, frame)
    (tmp_path / "png" / "left-behind.png").write_bytes(b"")
    manifest = _manifest(frames=(frame,))

    removed = purge_stale_artifacts(tmp_path, manifest)
    assert [path.name for path in removed] == ["left-behind.png"]

    # The frame's own PNG goes after the sweep, as a partial restore or an
    # interrupted copy leaves it. The manifest is never revisited.
    (tmp_path / frame.png).unlink()
    assert missing_artifacts(tmp_path, manifest) == (frame.png,)


def test_a_directory_that_lost_everything_names_every_claim(tmp_path: Path) -> None:
    """An empty directory is a total loss, not a clean run."""
    frame = _rendered("home--ready", "medium", "dark")
    manifest = _manifest(frames=(frame,))

    assert missing_artifacts(tmp_path, manifest) == (frame.png, frame.svg, frame.text)


def test_a_directory_entry_that_is_not_a_file_does_not_satisfy_a_claim(tmp_path: Path) -> None:
    """A directory standing where a frame should be is an absent frame.

    `exists()` would accept it. The walk asks for a file because the claim is
    about bytes.
    """
    frame = _rendered("home--ready", "medium", "dark")
    _run_directory_holding(tmp_path, frame)
    (tmp_path / frame.png).unlink()
    (tmp_path / frame.png).mkdir()
    manifest = _manifest(frames=(frame,))

    assert missing_artifacts(tmp_path, manifest) == (frame.png,)


def test_the_claim_walk_survives_the_real_write_and_read(tmp_path: Path) -> None:
    """Measured against a manifest that went through disk, not an in-memory one.

    The names are what the walk resolves, so a serializer that dropped or
    rewrote them would make the gate pass while measuring nothing.
    """
    frame = _rendered("home--ready", "medium", "dark")
    _run_directory_holding(tmp_path, frame)
    write_manifest(tmp_path, _manifest(frames=(frame,)))
    reloaded = read_manifest(tmp_path)

    assert missing_artifacts(tmp_path, reloaded) == ()
    (tmp_path / frame.text).unlink()
    assert missing_artifacts(tmp_path, reloaded) == (frame.text,)


def _written_run(root: Path, name: str, body: str) -> Path:
    """A real run directory: three files per frame and a manifest that names them.

    The digests are computed from the bytes actually written, so two runs
    built with different bodies genuinely differ and the diff has real work
    to do rather than short-circuiting on equal hashes.
    """
    directory = root / name
    frame = _rendered("home--ready", "medium", "dark")
    for relative, payload in (
        (frame.png, b"png-" + body.encode()),
        (frame.svg, b"<svg/>"),
        (frame.text, body.encode()),
    ):
        target = directory / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(payload)
    recorded = frame.model_copy(
        update={
            "png_sha256": digest(directory / frame.png),
            "text_sha256": digest(directory / frame.text),
        },
    )
    write_manifest(directory, _manifest(frames=(recorded,)))
    return directory


def test_the_diff_compares_two_runs_that_still_hold_what_they_claim(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The supported path, so the refusal below is a discrimination and not a block.

    Two runs whose frames genuinely differ: the command reports the change
    and exits 1 for that reason, which is the diff doing its job.
    """
    import typer

    from .. import _artifacts
    from ..cli import diff_command

    runs = tmp_path / "runs"
    monkeypatch.setattr(_artifacts, "RUNS_DIR", runs)
    _written_run(runs, "baseline", "before")
    _written_run(runs, "current", "after")

    with pytest.raises(typer.Exit) as reported:
        diff_command(baseline="baseline", highlight=False)
    assert reported.value.exit_code == 1


def test_the_diff_refuses_a_run_whose_manifest_outlives_its_frames(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The gate, driven through the command a reviewer actually runs.

    Without it the comparison reaches `_text_diff`, which opens the recorded
    text path directly: the operator gets a `FileNotFoundError` naming one
    file and saying nothing about which run is incomplete. Asserted as an
    `Exit` rather than a message so a reworded refusal does not break it,
    and paired with the explicit absence of the crash it replaces.
    """
    import typer

    from .. import _artifacts
    from ..cli import diff_command

    runs = tmp_path / "runs"
    monkeypatch.setattr(_artifacts, "RUNS_DIR", runs)
    baseline = _written_run(runs, "baseline", "before")
    _written_run(runs, "current", "after")
    lost = baseline / read_manifest(baseline).frames[0].text
    lost.unlink()

    with pytest.raises(typer.Exit) as refusal:
        diff_command(baseline="baseline", highlight=False)
    assert refusal.value.exit_code == 1
    assert not lost.exists(), "the refusal must not have repaired anything; it reports, it does not write"


def _payload_of(tmp_path: Path, manifest: Manifest) -> tuple[Path, dict[str, object]]:
    """Write ``manifest`` and hand back its path and its decoded payload."""
    path = write_manifest(tmp_path, manifest)
    return path, json.loads(path.read_text(encoding=UTF_8))


def test_a_manifest_this_tool_wrote_is_read_back(tmp_path: Path) -> None:
    """The positive half: the shape check must not refuse current output."""
    manifest = _manifest(frames=(_rendered("status", "small", "dark"),))
    write_manifest(tmp_path, manifest)

    assert read_manifest(tmp_path) == manifest


def test_a_manifest_written_before_a_defaulted_field_existed_is_refused(tmp_path: Path) -> None:
    """The half a version integer cannot see, and did not see.

    A field added with a default breaks nothing: every test that constructs a
    manifest keeps passing, every committed run keeps loading, and pydantic
    supplies the missing value in silence. So nothing makes the author bump
    :data:`MANIFEST_SCHEMA_VERSION`, and a run written by the older shape is
    then read as current -- which is precisely what the version exists to
    prevent. The refusal is what makes the coupling hold without an author
    remembering it.
    """
    path, payload = _payload_of(tmp_path, _manifest())
    del payload["skipped"]
    path.write_text(json.dumps(payload), encoding=UTF_8)

    with pytest.raises(ManifestVersionError) as refusal:
        read_manifest(tmp_path)
    message = str(refusal.value)
    assert "skipped" in message, "the refusal must name the field that moved"
    assert "render" in message, "the refusal must say how to recover"


def test_a_frame_written_before_a_defaulted_field_existed_is_refused(tmp_path: Path) -> None:
    """The same omission one level down: a frame, not the manifest header."""
    path, payload = _payload_of(tmp_path, _manifest(frames=(_rendered("status", "small", "dark"),)))
    frames = payload["frames"]
    assert isinstance(frames, list)
    del frames[0]["missing_glyphs"]
    path.write_text(json.dumps(payload), encoding=UTF_8)

    with pytest.raises(ManifestVersionError) as refusal:
        read_manifest(tmp_path)
    assert "frames[0]" in str(refusal.value)


def test_pydantic_alone_accepts_what_the_shape_check_refuses(tmp_path: Path) -> None:
    """Anti-tautology: prove the refusal is the new join, not validation.

    If pydantic already rejected these payloads the two tests above would pass
    against a check that does nothing. It does not: a defaulted field simply
    gets its default, which is the whole reason the omission was invisible.
    """
    _, payload = _payload_of(tmp_path, _manifest(frames=(_rendered("status", "small", "dark"),)))
    del payload["skipped"]
    frames = payload["frames"]
    assert isinstance(frames, list)
    del frames[0]["missing_glyphs"]

    accepted = Manifest.model_validate(payload)

    assert accepted.skipped == ()
    assert accepted.frames[0].missing_glyphs == ()
