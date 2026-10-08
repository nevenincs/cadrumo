"""Visual frame capture, retry, completeness, and publication reporting."""

from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path

import typer

from dev._paths import UTF_8

from . import _harness, _raster, _viewports
from ._artifacts import (
    SCRATCH_DIR,
    FailedFrame,
    FrameFailureKind,
    Manifest,
    RenderedFrame,
    SequenceProvenance,
    SkippedFrame,
    ThemeName,
    digest,
    unaccounted_frames,
)
from ._console import _echo


def _require_complete_render(
    manifest: Manifest,
    chosen_surfaces: tuple[str, ...],
    scenario_surfaces: tuple[str, ...],
    chosen_viewports: tuple[_viewports.Viewport, ...],
    chosen_themes: tuple[ThemeName, ...],
) -> None:
    """Require complete render."""
    unaccounted = unaccounted_frames(
        manifest,
        surfaces=(*chosen_surfaces, *scenario_surfaces),
        viewports=tuple(view.name for view in chosen_viewports),
        themes=tuple(chosen_themes),
    )
    if unaccounted:
        raise typer.BadParameter(
            "the run left frames unaccounted for, which would read as coverage it does not have: "
            + ", ".join(unaccounted[:5])
        )
    if manifest.spans_a_source_change:
        raise typer.BadParameter(
            "the TUI source changed while this run was rendering, so its frames come from two "
            "different builds and no reviewer can tell which is which. Nothing was written. "
            "Re-run against a settled tree."
        )


def _report_render_result(
    directory: Path,
    manifest: Manifest,
    frames: list[RenderedFrame],
    failures: list[FailedFrame],
    skipped: list[SkippedFrame],
    discarded: tuple[Path, ...],
    purge_refusal: str | None,
) -> None:
    """Report render result."""
    _echo("")
    _echo(f"wrote {len(frames)} frames to {directory}")
    _echo(f"index: {directory / 'index.md'}")
    if manifest.uncovered:
        _echo(f"{len(manifest.uncovered)} interfaces not rendered; see `inventory`")
    for name in manifest.blocked_surfaces:
        _report_blocked_surface(name, failures)
    if discarded:
        _echo(f"removed {len(discarded)} stale frames left by an earlier run")
    if purge_refusal is not None:
        _echo(f"stale frames kept: {purge_refusal}")
    if skipped:
        _echo(f"{len(skipped)} frames not attempted behind a refusing surface")
    if failures:
        _echo(f"{len(failures)} failed")
    if failures or purge_refusal is not None:
        raise typer.Exit(code=1)


def _attempt_scenario_capture(
    scenario: _harness.Scenario,
    viewports: tuple[_viewports.Viewport, ...],
    themes: tuple[ThemeName, ...],
    staging: Path,
    workspace: str,
    retries: int,
) -> tuple[
    tuple[SequenceProvenance, tuple[_harness.ScenarioCapture, ...], tuple[_harness.ScenarioRefusal, ...]] | None,
    str,
    FrameFailureKind,
    int,
]:
    """Attempt scenario capture."""
    outcome: (
        tuple[SequenceProvenance, tuple[_harness.ScenarioCapture, ...], tuple[_harness.ScenarioRefusal, ...]] | None
    ) = None
    detail, kind, made = "", FrameFailureKind.CRASHED, 0
    for attempt in range(1, retries + 2):
        made = attempt
        if staging.exists():
            shutil.rmtree(staging)
        try:
            outcome = _harness.capture_scenario(
                scenario.name,
                viewports,
                themes=themes,
                out_dir=staging,
                workspace=workspace,
            )
            break
        except _harness.HarnessError as refusal:
            detail, kind = str(refusal), refusal.kind
            if refusal.kind is FrameFailureKind.REFUSED:
                break
            if attempt <= retries:
                _echo(f"    {kind}; retrying ({attempt}/{retries})")
    return outcome, detail, kind, made


def _relative(path: Path, root: Path) -> str:
    return path.relative_to(root).as_posix()


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
    theme: ThemeName,
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
    kind = FrameFailureKind.CRASHED
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
            detail, kind = str(refusal), refusal.kind
            if refusal.kind is FrameFailureKind.REFUSED:
                break
        except _raster.RasterError as unpaintable:
            detail, kind = str(unpaintable), FrameFailureKind.RASTER
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


def _render_scenario(
    scenario: _harness.Scenario,
    directory: Path,
    *,
    viewports: tuple[_viewports.Viewport, ...],
    themes: tuple[ThemeName, ...],
    cell_height: int,
    retries: int,
    workspace: str,
    frames: list[RenderedFrame],
    failures: list[FailedFrame],
) -> None:
    """Render every page of one sequence scenario into the run, recording what failed.

    The harness writes a scenario's SVGs into a staging directory under
    ``scratch/``, never into the run, so a scenario that dies part way leaves
    no unclaimed SVG for the stale-frame sweep to meet. Each is moved into the
    run under the same stem an ordinary frame uses and rasterised the same way.
    """
    expected = len(scenario.pages) * len(viewports) * len(themes)
    _echo(f"[sequence {scenario.name}] {expected} frames: {scenario.summary}")
    staging = SCRATCH_DIR / f"sequence-{scenario.name}"
    outcome, detail, kind, made = _attempt_scenario_capture(scenario, viewports, themes, staging, workspace, retries)
    if outcome is None:
        _echo(f"    {kind} after {made} attempt(s)")
        failures.extend(
            FailedFrame(surface=surface, viewport=shape.name, theme=theme, kind=kind, attempts=made, detail=detail)
            for surface in scenario.pages.values()
            for shape in viewports
            for theme in themes
        )
        return

    provenance, captures, refusals = outcome
    if not provenance.matches_golden:
        _echo(f"    state DIVERGES from the golden for {provenance.sequence_id}; frames are recorded as such")
    for refused in refusals:
        failures.append(
            FailedFrame(
                surface=refused.surface,
                viewport=refused.viewport.name,
                theme=refused.theme,
                kind=FrameFailureKind.REFUSED,
                attempts=1,
                detail=refused.detail,
            ),
        )
    if refusals:
        _echo(f"    {len(refusals)} frame(s) refused: the declaration does not offer those pages")
    for item in captures:
        _commit_scenario_capture(item, directory, cell_height, provenance, frames, failures)
    shutil.rmtree(staging, ignore_errors=True)
    _echo(f"    {len(captures)} frames from {provenance.sequence_id} ({provenance.docs_page})")


@dataclass
class _RenderProgress:
    """One render matrix counter, including deliberately skipped frames."""

    total: int
    completed: int = 0


def _capture_matrix_frame(
    name: str,
    shape: _viewports.Viewport,
    appearance: ThemeName,
    refusal_reason: str | None,
    progress: _RenderProgress,
    directory: Path,
    run: str,
    locale: str | None,
    cell_height: int,
    retries: int,
    skip_refused: bool,
    frames: list[RenderedFrame],
    failures: list[FailedFrame],
    skipped: list[SkippedFrame],
) -> str | None:
    """Capture one matrix frame and retain the first refusal for its surface."""
    progress.completed += 1
    stem = f"{name}__{shape.name}__{appearance}"

    # A surface that already refused refuses at every geometry: the
    # guard runs while building the app, before layout. Attempting
    # the remaining frames costs a cold build per frame on the surfaces
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
        return refusal_reason

    _echo(f"[{progress.completed}/{progress.total}] {stem}")
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
        if outcome.kind is FrameFailureKind.REFUSED:
            refusal_reason = _first_refusal_line(outcome.detail)
        return refusal_reason

    captured, raster = outcome
    text_path.parent.mkdir(parents=True, exist_ok=True)
    text_path.write_text(captured.stable_text + "\n", encoding=UTF_8, newline="\n")
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
            cell_height=cell_height,
            elapsed_ms=captured.elapsed_ms,
            geometry_findings=captured.geometry_findings,
            missing_glyphs=raster.missing_glyphs,
        ),
    )
    return refusal_reason


def _render_surface(
    name: str,
    viewports: tuple[_viewports.Viewport, ...],
    themes: tuple[ThemeName, ...],
    progress: _RenderProgress,
    directory: Path,
    run: str,
    locale: str | None,
    cell_height: int,
    retries: int,
    skip_refused: bool,
    frames: list[RenderedFrame],
    failures: list[FailedFrame],
    skipped: list[SkippedFrame],
) -> None:
    """Render one surface across its geometry and appearance matrix."""
    refusal_reason: str | None = None
    for shape in viewports:
        for appearance in themes:
            refusal_reason = _capture_matrix_frame(
                name,
                shape,
                appearance,
                refusal_reason,
                progress,
                directory,
                run,
                locale,
                cell_height,
                retries,
                skip_refused,
                frames,
                failures,
                skipped,
            )


def _commit_scenario_capture(
    item: _harness.ScenarioCapture,
    directory: Path,
    cell_height: int,
    provenance: SequenceProvenance,
    frames: list[RenderedFrame],
    failures: list[FailedFrame],
) -> None:
    """Commit scenario capture."""
    captured = item.capture
    stem = f"{captured.surface}__{captured.viewport.name}__{captured.theme}"
    svg_path = directory / "svg" / f"{stem}.svg"
    png_path = directory / "png" / f"{stem}.png"
    text_path = directory / "text" / f"{stem}.txt"
    svg_path.parent.mkdir(parents=True, exist_ok=True)
    captured.svg_path.replace(svg_path)
    try:
        raster = _raster.rasterise(svg_path, png_path, cell_height=cell_height)
    except _raster.RasterError as unpaintable:
        failures.append(
            FailedFrame(
                surface=captured.surface,
                viewport=captured.viewport.name,
                theme=captured.theme,
                kind=FrameFailureKind.RASTER,
                detail=str(unpaintable),
            ),
        )
        return
    text_path.parent.mkdir(parents=True, exist_ok=True)
    text_path.write_text(captured.stable_text + "\n", encoding=UTF_8, newline="\n")
    frames.append(
        RenderedFrame(
            surface=captured.surface,
            viewport=captured.viewport.name,
            columns=captured.viewport.columns,
            rows=captured.viewport.rows,
            orientation=captured.viewport.orientation,
            theme=captured.theme,
            png=_relative(png_path, directory),
            svg=_relative(svg_path, directory),
            text=_relative(text_path, directory),
            png_sha256=digest(png_path),
            text_sha256=digest(text_path),
            cell_height=cell_height,
            elapsed_ms=captured.elapsed_ms,
            geometry_findings=captured.geometry_findings,
            missing_glyphs=raster.missing_glyphs,
            sequence=provenance,
        ),
    )


def _report_blocked_surface(name: str, failures: list[FailedFrame]) -> None:
    """Report blocked surface."""
    reason = next(
        (_first_refusal_line(entry.detail) for entry in failures if entry.surface == name),
        "no diagnostics",
    )
    _echo(f"blocked: {name} produced no frame — {reason}")
