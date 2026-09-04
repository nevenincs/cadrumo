"""The TUI visual inventory command line.

Five verbs. ``inventory`` answers what interfaces exist and which of them a
render reaches; ``render`` produces the images; ``rasterise`` repaints an
existing run without re-driving the harness; ``diff`` compares one run against
another; ``viewports`` prints the geometries a render covers.

Rendering shells out to the in-boundary devtool harness once per frame, so a
full matrix is minutes rather than seconds -- each frame rebuilds its app
from birth, and the surfaces that need a profile pay real key derivation.
That cost buys the property that makes the artefacts worth reviewing: no
frame is a cached statement about a tree that existed earlier.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Annotated

import typer

from .._paths import UTF_8
from . import _coverage, _diff, _harness, _inventory, _raster, _viewports
from ._artifacts import (
    DEFAULT_RUN_NAME,
    FailedFrame,
    InterfaceRecord,
    Manifest,
    ManifestVersionError,
    RenderedFrame,
    SkippedFrame,
    digest,
    known_runs,
    now,
    read_manifest,
    run_directory,
    write_index,
    write_manifest,
)

app = typer.Typer(
    name="tui",
    help="Render every registered TUI surface to disk for visual review.",
    no_args_is_help=True,
    add_completion=False,
)

THEMES = ("dark", "light")
DEFAULT_RUN = DEFAULT_RUN_NAME


def _echo(text: str) -> None:
    """Write a line as UTF-8 whatever the console code page claims.

    Written as bytes rather than through ``print``: a Windows console defaults
    to cp1252, which mangles the box-drawing and dash characters the harness's
    own diagnostics are built from -- the same reason the in-boundary harness
    encodes its output by hand.
    """
    sys.stdout.buffer.write(text.encode(UTF_8, errors="replace") + b"\n")
    sys.stdout.buffer.flush()


def _relative(path: Path, root: Path) -> str:
    return path.relative_to(root).as_posix()


@app.command("viewports")
def viewports_command() -> None:
    """List the terminal geometries a render can cover."""
    for viewport in _viewports.VIEWPORTS.values():
        default = " (default)" if viewport.name in _viewports.DEFAULT_VIEWPORTS else ""
        _echo(f"{viewport.name:<10} {viewport.label:>8}  {viewport.orientation:<9} {viewport.summary}{default}")


@app.command("runs")
def runs_command() -> None:
    """List every review run on disk, newest first.

    A partial run is marked. Nine directories once sat side by side with no way
    to tell a forty-frame review from a three-frame experiment, which is what
    made the artefact tree untrustworthy to review from.
    """
    entries = known_runs()
    if not entries:
        _echo(f"no runs yet; render one with `python -m dev.tui render` -> runs/{DEFAULT_RUN_NAME}/")
        return
    rows = []
    for directory in entries:
        try:
            manifest = read_manifest(directory)
        except (ManifestVersionError, FileNotFoundError) as refusal:
            rows.append((directory.name, "", f"unreadable: {refusal}"))
            continue
        state = "complete"
        if manifest.failures or manifest.skipped:
            state = f"PARTIAL ({len(manifest.failures)} failed, {len(manifest.skipped)} skipped)"
        marker = "  <- default" if directory.name == DEFAULT_RUN_NAME else ""
        rows.append((directory.name, manifest.generated_at, f"{len(manifest.frames):3} frames  {state}{marker}"))
    for name, stamp, detail in sorted(rows, key=lambda row: row[1], reverse=True):
        _echo(f"{name:<16} {stamp:<26} {detail}")


@app.command("inventory")
def inventory_command(
    run: Annotated[str, typer.Option("--run", help="Run whose coverage to report.")] = DEFAULT_RUN,
) -> None:
    """List every TUI interface the source tree defines, and its coverage.

    The list is derived by reading the source, so it is complete by
    construction rather than by a maintained count. Coverage is read from the
    named run's manifest when one exists, and from the coverage table alone
    when it does not.
    """
    interfaces = _inventory.scan()
    surfaces = tuple(surface.name for surface in _harness.surfaces())
    table = _coverage.merge_rendered_by(_harness.coverage())
    _coverage.check(interfaces, surfaces, rendered_table=table)
    resolved_notes = _coverage.notes(table)

    directory = run_directory(run)
    rendered: dict[str, tuple[str, ...]] = {}
    if (directory / "manifest.json").is_file():
        manifest = _load_manifest(run)
        rendered = {record.qualname: record.rendered_by for record in manifest.interfaces}
        _echo(f"coverage from run {run!r} ({manifest.generated_at})")
    else:
        rendered = {
            interface.qualname: _coverage.rendered_by(interface.qualname, surfaces, rendered_table=table)
            for interface in interfaces
        }
        _echo(f"no run named {run!r}; showing what the coverage table claims")
    _echo("")

    uncovered = 0
    for interface in interfaces:
        covered_by = rendered.get(interface.qualname, ())
        if covered_by:
            mark = ", ".join(covered_by)
        else:
            mark = "NOT RENDERED"
            uncovered += 1
        note = resolved_notes.get(interface.qualname, "")
        suffix = f"  [{note}]" if note else ""
        locator = f"{interface.path.as_posix()}:{interface.line}"
        _echo(f"{interface.kind:<6} {interface.qualname}")
        _echo(f"       {locator}")
        _echo(f"       {mark}{suffix}")
    _echo("")
    _echo(f"{len(interfaces)} interfaces, {uncovered} not rendered")


def _load_manifest(name: str) -> Manifest:
    """Read a run's manifest, turning its refusals into clean CLI exits.

    A stale or absent run is an ordinary operator mistake, not a bug, so it
    earns a sentence and a non-zero exit rather than a stack trace.
    """
    try:
        return read_manifest(run_directory(name))
    except (FileNotFoundError, ManifestVersionError) as refusal:
        _echo(str(refusal))
        raise typer.Exit(code=1) from None


def _first_refusal_line(detail: str) -> str:
    """The harness's own one-line reason, out of its multi-line diagnostics."""
    for line in detail.splitlines():
        stripped = line.strip()
        if stripped.startswith("refused:"):
            return stripped.removeprefix("refused:").strip()
    return detail.splitlines()[0] if detail else "no diagnostics"


def _attempt_frame(
    surface: str,
    shape: _viewports.Viewport,
    *,
    theme: str,
    svg_path: Path,
    png_path: Path,
    locale: str | None,
    workspace: str,
    cell_height: int,
    retries: int,
) -> tuple[_harness.Capture, _raster.RasterResult] | FailedFrame:
    """Capture and rasterise one frame, retrying only what a retry can fix.

    A CRASHED harness earns another go: the usual cause in a shared worktree
    is a module caught half-edited by a peer, and the next attempt often finds
    the tree whole again. A REFUSED harness does not, because the answer came
    from an application guard that will give the same answer to the same
    question. Retrying a refusal would multiply the slowest surfaces' cost by
    the retry count and change nothing.
    """
    detail = ""
    kind = _harness.FailureKind.CRASHED.value
    made = 0
    for attempt in range(1, retries + 2):
        made = attempt
        try:
            captured = _harness.capture(
                surface,
                shape,
                theme=theme,
                svg_path=svg_path,
                locale=locale,
                workspace=workspace,
            )
            raster = _raster.rasterise(svg_path, png_path, cell_height=cell_height)
        except _harness.HarnessError as refusal:
            detail, kind = str(refusal), refusal.kind.value
            if refusal.kind is _harness.FailureKind.REFUSED:
                break
        except _raster.RasterError as unpaintable:
            # The harness produced a frame; this tool could not repaint it.
            # Never retried: the SVG on disk is identical next time.
            detail, kind = str(unpaintable), "raster"
            break
        else:
            return captured, raster
        if attempt <= retries:
            _echo(f"    {kind}; retrying ({attempt}/{retries})")
    return FailedFrame(
        surface=surface,
        viewport=shape.name,
        theme=theme,
        kind=kind,
        attempts=made,
        detail=detail,
    )


def _resolve_viewports(names: list[str] | None) -> tuple[_viewports.Viewport, ...]:
    chosen = tuple(names) if names else _viewports.DEFAULT_VIEWPORTS
    if len(chosen) == 1 and chosen[0] == "all":
        chosen = tuple(_viewports.VIEWPORTS)
    return tuple(_viewports.resolve(name) for name in chosen)


def _resolve_surfaces(names: list[str] | None, available: tuple[_harness.Surface, ...]) -> tuple[str, ...]:
    known = {surface.name for surface in available}
    if not names:
        return tuple(sorted(known))
    unknown = sorted(set(names) - known)
    if unknown:
        accepted = ", ".join(sorted(known))
        message = f"unknown surface(s) {', '.join(unknown)}; accepted: {accepted}"
        raise typer.BadParameter(message)
    return tuple(names)


@app.command("render")
def render_command(
    surface: Annotated[
        list[str] | None,
        typer.Option("--surface", "-s", help="Render only this surface; repeatable. Omit for all."),
    ] = None,
    viewport: Annotated[
        list[str] | None,
        typer.Option("--viewport", "-v", help="Render at this viewport; repeatable, or 'all'."),
    ] = None,
    theme: Annotated[
        list[str] | None,
        typer.Option("--theme", "-t", help="Render under this appearance; repeatable."),
    ] = None,
    cell_height: Annotated[
        int,
        typer.Option("--cell-height", help="Pixel height of one terminal cell; raises the output resolution."),
    ] = _raster.DEFAULT_CELL_HEIGHT,
    locale: Annotated[
        str | None,
        typer.Option("--locale", help="Force an output language; omit to resolve ambiently."),
    ] = None,
    retries: Annotated[
        int,
        typer.Option("--retries", min=0, help="Extra attempts for a CRASHED harness; refusals are never retried."),
    ] = 1,
    skip_refused: Annotated[
        bool,
        typer.Option(
            "--skip-refused/--no-skip-refused",
            help="After a surface refuses, record its remaining frames as skipped instead of re-asking.",
        ),
    ] = True,
) -> None:
    """Render surfaces to PNG and SVG into the canonical review directory.

    There is deliberately no `--run` here. The review path is a CONTRACT, not
    a per-invocation choice: `runs/current` is where a render lands, always,
    so the reviewer opens one path and never has to be told which of nine
    directories the last session happened to name. To keep a run for later
    comparison, take a `snapshot` of it under a name; that is an explicit act
    with an explicit name, rather than a render quietly aimed somewhere else.
    """
    run = DEFAULT_RUN_NAME
    available = _harness.surfaces()
    interfaces = _inventory.scan()
    coverage_table = _coverage.merge_rendered_by(_harness.coverage())
    coverage_notes = _coverage.notes(coverage_table)
    _coverage.check(interfaces, tuple(item.name for item in available), rendered_table=coverage_table)

    chosen_surfaces = _resolve_surfaces(surface, available)
    chosen_viewports = _resolve_viewports(viewport)
    chosen_themes = tuple(theme) if theme else THEMES
    for name in chosen_themes:
        if name not in THEMES:
            raise typer.BadParameter(f"unknown theme {name!r}; accepted: {', '.join(THEMES)}")

    directory = run_directory(run)
    directory.mkdir(parents=True, exist_ok=True)

    frames: list[RenderedFrame] = []
    failures: list[FailedFrame] = []
    skipped: list[SkippedFrame] = []
    total = len(chosen_surfaces) * len(chosen_viewports) * len(chosen_themes)
    index = 0

    for name in chosen_surfaces:
        refusal_reason: str | None = None
        for shape in chosen_viewports:
            for appearance in chosen_themes:
                index += 1
                stem = f"{name}__{shape.name}__{appearance}"

                # A surface that already refused refuses at every geometry: the
                # guard runs while building the app, before layout. Attempting
                # the remaining frames costs minutes per frame on the surfaces
                # that provision a real encrypted profile, and buys a reviewer
                # nothing but the same sentence repeated.
                if refusal_reason is not None and skip_refused:
                    skipped.append(
                        SkippedFrame(
                            surface=name,
                            viewport=shape.name,
                            theme=appearance,
                            reason=f"surface already refused: {refusal_reason}",
                        ),
                    )
                    continue

                _echo(f"[{index}/{total}] {stem}")
                svg_path = directory / "svg" / f"{stem}.svg"
                png_path = directory / "png" / f"{stem}.png"
                text_path = directory / "text" / f"{stem}.txt"

                outcome = _attempt_frame(
                    name,
                    shape,
                    theme=appearance,
                    svg_path=svg_path,
                    png_path=png_path,
                    locale=locale,
                    workspace=f"visual-inventory-{run}",
                    cell_height=cell_height,
                    retries=retries,
                )
                if isinstance(outcome, FailedFrame):
                    _echo(f"    {outcome.kind} after {outcome.attempts} attempt(s)")
                    failures.append(outcome)
                    if outcome.kind == _harness.FailureKind.REFUSED.value:
                        refusal_reason = _first_refusal_line(outcome.detail)
                    continue

                captured, raster = outcome
                text_path.parent.mkdir(parents=True, exist_ok=True)
                text_path.write_text(captured.stable_text + "\n", encoding=UTF_8)
                frames.append(
                    RenderedFrame(
                        surface=name,
                        viewport=shape.name,
                        columns=shape.columns,
                        rows=shape.rows,
                        orientation=shape.orientation,
                        theme=appearance,
                        png=_relative(png_path, directory),
                        svg=_relative(svg_path, directory),
                        text=_relative(text_path, directory),
                        png_sha256=digest(png_path),
                        text_sha256=digest(text_path),
                        elapsed_ms=captured.elapsed_ms,
                        geometry_findings=captured.geometry_findings,
                        missing_glyphs=raster.missing_glyphs,
                    ),
                )

    rendered_surfaces = tuple(sorted({frame.surface for frame in frames}))
    manifest = Manifest(
        generated_at=now(),
        cell_height=cell_height,
        frames=tuple(frames),
        interfaces=tuple(
            InterfaceRecord(
                qualname=item.qualname,
                kind=item.kind,
                locator=f"{item.path.as_posix()}:{item.line}",
                rendered_by=_coverage.rendered_by(item.qualname, rendered_surfaces, rendered_table=coverage_table),
                note=coverage_notes.get(item.qualname, ""),
            )
            for item in interfaces
        ),
        failures=tuple(failures),
        skipped=tuple(skipped),
    )
    write_manifest(directory, manifest)
    write_index(directory, manifest)

    _echo("")
    _echo(f"wrote {len(frames)} frames to {directory}")
    _echo(f"index: {directory / 'index.md'}")
    if manifest.uncovered:
        _echo(f"{len(manifest.uncovered)} interfaces not rendered; see `inventory`")
    for name in manifest.blocked_surfaces:
        reason = next(
            (_first_refusal_line(entry.detail) for entry in failures if entry.surface == name),
            "no diagnostics",
        )
        _echo(f"blocked: {name} produced no frame — {reason}")
    if skipped:
        _echo(f"{len(skipped)} frames not attempted behind a refusing surface")
    if failures:
        _echo(f"{len(failures)} failed")
        raise typer.Exit(code=1)


@app.command("snapshot")
def snapshot_command(
    name: Annotated[str, typer.Argument(help="Name to keep the current review under.")],
) -> None:
    """Copy the canonical review aside so a later render can be diffed against it.

    The only sanctioned way to create a second run directory. Rendering itself
    always targets `runs/current`, so a named run can only ever be a
    deliberate snapshot of a review that actually happened.
    """
    import shutil

    if name == DEFAULT_RUN_NAME:
        _echo(f"{name!r} is the canonical review; choose another name for a snapshot")
        raise typer.Exit(code=1)

    source = run_directory(DEFAULT_RUN_NAME)
    if not (source / "manifest.json").is_file():
        _echo(f"nothing to snapshot: {source} holds no run")
        raise typer.Exit(code=1)

    destination = run_directory(name)
    if destination.exists():
        shutil.rmtree(destination)
    shutil.copytree(source, destination)
    _echo(f"snapshot: {destination}")


@app.command("rasterise")
def rasterise_command(
    run: Annotated[str, typer.Option("--run", help="Run whose SVGs to repaint.")] = DEFAULT_RUN,
    cell_height: Annotated[
        int,
        typer.Option("--cell-height", help="Pixel height of one terminal cell."),
    ] = _raster.DEFAULT_CELL_HEIGHT,
) -> None:
    """Repaint an existing run's PNGs from the SVGs it already holds.

    The harness is not driven at all. A run's SVGs are the harness's own
    output and stay valid however this tool's rasteriser changes, so fixing a
    rendering defect -- or simply wanting the frames at another resolution --
    should not cost another full matrix at minutes per frame. Only the
    raster-derived fields are rewritten; the captured text, the timings and
    the geometry readings still belong to the run that produced them.
    """
    directory = run_directory(run)
    manifest = _load_manifest(run)
    if not manifest.frames:
        _echo(f"run {run!r} holds no frames to repaint")
        raise typer.Exit(code=1)

    repainted: list[RenderedFrame] = []
    missing_svgs: list[str] = []
    for index, frame in enumerate(manifest.frames, start=1):
        svg_path = directory / frame.svg
        if not svg_path.is_file():
            _echo(f"[{index}/{len(manifest.frames)}] {frame.key} — SVG missing, kept as recorded")
            missing_svgs.append(frame.key)
            repainted.append(frame)
            continue
        _echo(f"[{index}/{len(manifest.frames)}] {frame.key}")
        png_path = directory / frame.png
        raster = _raster.rasterise(svg_path, png_path, cell_height=cell_height)
        repainted.append(
            frame.model_copy(
                update={
                    "png_sha256": digest(png_path),
                    "missing_glyphs": raster.missing_glyphs,
                },
            ),
        )

    updated = manifest.model_copy(update={"cell_height": cell_height, "frames": tuple(repainted)})
    write_manifest(directory, updated)
    write_index(directory, updated)

    _echo("")
    _echo(f"repainted {len(manifest.frames) - len(missing_svgs)} frames at cell height {cell_height}")
    if missing_svgs:
        _echo(f"{len(missing_svgs)} frames had no SVG and were left as recorded")
        raise typer.Exit(code=1)


@app.command("diff")
def diff_command(
    baseline: Annotated[str, typer.Argument(help="Run to compare against.")],
    candidate: Annotated[str, typer.Option("--against", help="Run to compare.")] = DEFAULT_RUN,
    highlight: Annotated[
        bool,
        typer.Option("--highlight/--no-highlight", help="Write side-by-side images for changed frames."),
    ] = True,
) -> None:
    """Report what changed between two runs."""
    baseline_root, candidate_root = run_directory(baseline), run_directory(candidate)
    before, after = _load_manifest(baseline), _load_manifest(candidate)
    diffs = _diff.compare(baseline_root, before, candidate_root, after)
    _echo(_diff.render_report(diffs))

    changed = [entry for entry in diffs if entry.change is _diff.Change.CHANGED]
    if highlight and changed:
        destination_root = candidate_root / "diff" / baseline
        frames = {frame.key: frame for frame in after.frames}
        baseline_frames = {frame.key: frame for frame in before.frames}
        written = 0
        for entry in changed:
            stem = entry.key.replace("/", "__")
            if entry.text_diff:
                (destination_root / f"{stem}.diff").parent.mkdir(parents=True, exist_ok=True)
                (destination_root / f"{stem}.diff").write_text(entry.text_diff + "\n", encoding=UTF_8)
            produced = _diff.write_highlight(
                baseline_root / baseline_frames[entry.key].png,
                candidate_root / frames[entry.key].png,
                destination_root / f"{stem}.png",
            )
            written += 1 if produced is not None else 0
        _echo("")
        _echo(f"wrote {written} highlight images to {destination_root}")

    if changed or any(entry.change is not _diff.Change.UNCHANGED for entry in diffs):
        raise typer.Exit(code=1)


__all__ = ["app"]
