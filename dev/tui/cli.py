"""The TUI visual inventory command line.

The package README carries the verb inventory, and a test joins it to the
registrations below, so this docstring deliberately does not restate it: an
enumeration kept in two places drifted in one of them, which is how ``runs``
and ``snapshot`` came to be undocumented verbs.

Rendering shells out to the development harness once per frame, so a
full matrix is tens of minutes rather than seconds -- each frame starts an
interpreter and rebuilds its app from birth, a few seconds apiece, and the
surfaces that need a profile also pay real key derivation.
That cost buys the property that makes the artefacts worth reviewing: no
frame is a cached statement about a tree that existed earlier.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated

import typer

from dev._paths import UTF_8

from . import _coverage, _diff, _harness, _inventory, _raster, _viewports
from ._artifacts import (
    DEFAULT_RUN_NAME,
    RUNS_DIR,
    FailedFrame,
    InterfaceRecord,
    Manifest,
    ManifestVersionError,
    RenderedFrame,
    SkippedFrame,
    StaleArtifactPurgeRefusedError,
    ThemeName,
    commit_staged_run,
    digest,
    known_runs,
    missing_artifacts,
    now,
    purge_stale_artifacts,
    read_manifest,
    run_directory,
    snapshot_staging_directory,
    source_fingerprint,
    stage_run_copy,
    write_index,
    write_manifest,
)
from ._console import _echo
from ._render import _render_scenario, _render_surface, _RenderProgress, _report_render_result, _require_complete_render
from ._review_catalogue import ReviewCatalogue, RunView
from ._review_network import TailnetUnavailableError, is_wildcard_host, tailnet_node
from ._review_server import ReviewHTTPServer, serve
from ._review_server_contracts import DEFAULT_REVIEW_PORT
from ._review_state import ReviewState
from ._review_store import Note, NoteImageState, ReviewStore, ReviewStoreVersionError, image_state

app = typer.Typer(
    name="tui",
    help="Render every registered TUI surface to disk for visual review.",
    no_args_is_help=True,
    add_completion=False,
)


THEMES = tuple(ThemeName)
"""Every appearance a render may be asked for, in declaration order.

Derived from the vocabulary rather than restating it: this tuple used to
be the only place the two words were written down, and nothing that
RECORDED a theme consulted it.
"""


DEFAULT_RUN = DEFAULT_RUN_NAME


def _choose_render_subjects(
    surface: list[str] | None,
    sequence: list[str] | None,
    available: tuple[_harness.Surface, ...],
    available_scenarios: tuple[_harness.Scenario, ...],
) -> tuple[tuple[str, ...], tuple[_harness.Scenario, ...]]:
    """Choose render subjects."""
    chosen_surfaces = _resolve_surfaces(surface, available) if surface or not sequence else ()
    if sequence:
        chosen_scenarios = _resolve_scenarios(sequence, available_scenarios)
    else:
        chosen_scenarios = () if surface else available_scenarios
    return chosen_surfaces, chosen_scenarios


def _note_readings(
    notes: tuple[Note, ...], view: RunView | None
) -> list[tuple[Note, NoteImageState, NoteImageState | None]]:
    """Note readings."""
    elements = {} if view is None else {element.key: element.digest for element in view.elements}
    frames = {} if view is None else {frame.key: frame.png_sha256 for frame in view.frames}
    readings = [
        (
            note,
            image_state(note.element_sha256, elements.get(note.element_key)),
            None
            if note.frame_key is None or note.frame_sha256 is None
            else image_state(note.frame_sha256, frames.get(note.frame_key)),
        )
        for note in notes
    ]
    return readings


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
    surfaces = _harness.reviewable_surface_names(_harness.surfaces(), _harness.scenarios())
    table = _harness.coverage()
    _coverage.check(interfaces, surfaces, rendered_table=table)
    resolved_notes = _coverage.notes(interfaces, surfaces, rendered_table=table)

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
        elif interface.is_base:
            mark = "STRUCTURAL BASE"
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


def _resolve_viewports(names: list[str] | None) -> tuple[_viewports.Viewport, ...]:
    chosen = tuple(names) if names else _viewports.DEFAULT_VIEWPORTS
    if len(chosen) == 1 and chosen[0] == "all":
        chosen = tuple(_viewports.VIEWPORTS)
    return tuple(_viewports.resolve(name) for name in chosen)


def _resolve_themes(names: list[str] | None) -> tuple[ThemeName, ...]:
    if not names:
        return THEMES
    chosen: list[ThemeName] = []
    for name in names:
        try:
            chosen.append(ThemeName(name))
        except ValueError:
            accepted = ", ".join(THEMES)
            raise typer.BadParameter(f"unknown theme {name!r}; accepted: {accepted}") from None
    return tuple(chosen)


def _resolve_scenarios(names: list[str], available: tuple[_harness.Scenario, ...]) -> tuple[_harness.Scenario, ...]:
    if names == ["all"]:
        return available
    known = {scenario.name: scenario for scenario in available}
    unknown = sorted(set(names) - set(known))
    if unknown:
        accepted = ", ".join(sorted(known))
        raise typer.BadParameter(f"unknown sequence scenario(s) {', '.join(unknown)}; accepted: {accepted}")
    return tuple(known[name] for name in names)


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
    sequence: Annotated[
        list[str] | None,
        typer.Option(
            "--sequence",
            "-q",
            help="Render only this sequence scenario; repeatable, or 'all' for every scenario and no surfaces.",
        ),
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

    Sequence scenarios render after the surfaces: each runs its documentation
    sequence once and captures every Modelo workspace page over the
    declaration it built. `--surface` and `--sequence` each narrow the render
    to what they name; with neither, both kinds render.
    """
    run = DEFAULT_RUN_NAME
    available = _harness.surfaces()
    available_scenarios = _harness.scenarios()
    interfaces = _inventory.scan()
    coverage_table = _harness.coverage()
    available_names = _harness.reviewable_surface_names(available, available_scenarios)
    coverage_notes = _coverage.notes(interfaces, available_names, rendered_table=coverage_table)

    # Naming either kind narrows the render to what was named; naming neither
    # renders everything, surfaces and scenarios alike.
    chosen_surfaces, chosen_scenarios = _choose_render_subjects(surface, sequence, available, available_scenarios)
    chosen_viewports = _resolve_viewports(viewport)
    chosen_themes = _resolve_themes(theme)

    directory = run_directory(run)
    directory.mkdir(parents=True, exist_ok=True)

    # Taken BEFORE the first frame, compared after the last: a full matrix runs
    # for tens of minutes, and an edit landing inside that window
    # produces a set that is half old and half new while the manifest reports
    # every frame as current.
    source_at_start = source_fingerprint()

    frames: list[RenderedFrame] = []
    failures: list[FailedFrame] = []
    skipped: list[SkippedFrame] = []
    total = len(chosen_surfaces) * len(chosen_viewports) * len(chosen_themes)
    scenario_surfaces = tuple(page for scenario in chosen_scenarios for page in scenario.pages.values())
    progress = _RenderProgress(total=total)

    for name in chosen_surfaces:
        _render_surface(
            name,
            chosen_viewports,
            chosen_themes,
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

    for scenario in chosen_scenarios:
        _render_scenario(
            scenario,
            directory,
            viewports=chosen_viewports,
            themes=chosen_themes,
            cell_height=cell_height,
            retries=retries,
            workspace=f"visual-inventory-{run}",
            frames=frames,
            failures=failures,
        )

    rendered_surfaces = tuple(sorted({frame.surface for frame in frames}))
    manifest = Manifest(
        generated_at=now(),
        source_revision=source_at_start,
        source_revision_at_end=source_fingerprint(),
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
    _require_complete_render(manifest, chosen_surfaces, scenario_surfaces, chosen_viewports, chosen_themes)
    # Written BEFORE the sweep, not after. The sweep is the only destructive
    # step in a command that takes tens of minutes, and running it
    # first meant any refusal or filesystem error inside it discarded the
    # manifest and index of a render that had already succeeded.
    write_manifest(directory, manifest)
    write_index(directory, manifest)

    discarded: tuple[Path, ...] = ()
    purge_refusal: str | None = None
    try:
        discarded = purge_stale_artifacts(directory, manifest)
    except StaleArtifactPurgeRefusedError as exc:
        purge_refusal = str(exc)

    _report_render_result(directory, manifest, frames, failures, skipped, discarded, purge_refusal)


@app.command("snapshot")
def snapshot_command(
    name: Annotated[str, typer.Argument(help="Name to keep the current review under.")],
    replace: Annotated[
        bool,
        typer.Option(
            "--replace",
            help="Discard an existing snapshot of this name. Destructive; refused by default.",
        ),
    ] = False,
) -> None:
    """Copy the canonical review aside so a later render can be diffed against it.

    The only sanctioned way to create a second run directory. Rendering itself
    always targets `runs/current`, so a named run can only ever be a
    deliberate snapshot of a review that actually happened.

    A name already taken is REFUSED. Runs are gitignored and a full matrix
    costs tens of minutes, so an existing snapshot is the only
    copy of the review it holds; overwriting it on a bare name collision
    would destroy the evidence this verb exists to keep. ``--replace`` is
    how an operator says the older review is finished with.
    """
    if name == DEFAULT_RUN_NAME:
        _echo(f"{name!r} is the canonical review; choose another name for a snapshot")
        raise typer.Exit(code=1)

    source = run_directory(DEFAULT_RUN_NAME)
    if not (source / "manifest.json").is_file():
        _echo(f"nothing to snapshot: {source} holds no run")
        raise typer.Exit(code=1)

    destination = run_directory(name)
    if destination.exists() and not replace:
        held = sum(1 for path in destination.rglob("*") if path.is_file())
        _echo(
            f"snapshot {name!r} already exists at {destination} and holds {held} file(s). "
            "Nothing was written. Choose another name, or pass --replace to discard it."
        )
        raise typer.Exit(code=1)
    # Staged, then swapped. The copy is completed under `scratch/` first and
    # only then replaces the destination, so the irreversible removal runs
    # AFTER its replacement is durable rather than before it is begun. In
    # place, a copy that failed part way through a run of hundreds of files
    # left the named snapshot destroyed and half-rebuilt -- and still
    # carrying a manifest, so `known_runs` listed the wreckage as a review.
    staging = snapshot_staging_directory(destination)
    stage_run_copy(source, staging)
    # Re-checked rather than trusted: only the exact path the refusal was
    # measured against is removed.
    commit_staged_run(staging, destination)
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
    should not cost another full matrix at seconds per frame. Only the
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
                    "cell_height": cell_height,
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
        _echo(
            "their PNGs are still at the cell height they were painted at, which the "
            "manifest records per frame: " + ", ".join(sorted(missing_svgs))
        )
        raise typer.Exit(code=1)


def _refuse_a_run_whose_manifest_outlives_its_frames(name: str, directory: Path, manifest: Manifest) -> None:
    """Refuse a comparison whose inputs are claims without bytes.

    The manifest is the only side anything walked. `stale_artifacts` asks
    which files the manifest fails to name; nothing asked which names fail
    to find a file, so a run that lost frames after its manifest was
    written still reads as complete everywhere a reviewer looks. The diff
    then opens a recorded path and raises `FileNotFoundError`, which names
    one file and says nothing about the run it came from.
    """
    absent = missing_artifacts(directory, manifest)
    if not absent:
        return
    _echo(
        f"run {name!r} names {len(absent)} file(s) its directory does not hold, so its manifest "
        "claims frames that are not there. Nothing was compared; re-render or repaint the run. "
        + ", ".join(absent[:10]),
    )
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
    _refuse_a_run_whose_manifest_outlives_its_frames(baseline, baseline_root, before)
    _refuse_a_run_whose_manifest_outlives_its_frames(candidate, candidate_root, after)
    diffs = _diff.compare(baseline_root, before, candidate_root, after)
    _echo(_diff.render_report(diffs))

    changed = [entry for entry in diffs if entry.change is _diff.Change.CHANGED]
    if highlight and changed:
        _write_diff_highlights(baseline, baseline_root, candidate_root, before, after, changed)

    if changed or any(entry.change is not _diff.Change.UNCHANGED for entry in diffs):
        raise typer.Exit(code=1)


def _url(host: str, port: int) -> str:
    return f"http://[{host}]:{port}/" if ":" in host else f"http://{host}:{port}/"


@app.command("serve")
def serve_command(
    host: Annotated[
        str | None,
        typer.Option("--host", help="Address to listen on. Omit to bind this machine's tailnet address only."),
    ] = None,
    port: Annotated[int, typer.Option("--port", min=1, max=65535, help="TCP port to listen on.")] = DEFAULT_REVIEW_PORT,
) -> None:
    """Serve the review runs to a browser, live, with notes kept on this machine.

    Frames appear in the page as the render writes them, so a render can be
    reviewed while it is still running. The page groups them by the element
    they show, and notes and sign-offs are kept per element, in a database
    outside the run tree that survives the server stopping, a re-render, and a
    snapshot being replaced.

    The default bind is the tailnet address and nothing else: the tailnet is
    the only access control this server has. A wildcard address is refused.
    """
    name: str | None = None
    if host is None:
        try:
            node = tailnet_node()
        except TailnetUnavailableError as refusal:
            _echo(f"cannot bind the tailnet: {refusal}. Pass --host 127.0.0.1 to review on this machine only.")
            raise typer.Exit(code=1) from None
        address, name = node.address, node.name
    elif is_wildcard_host(host):
        _echo(f"refusing to listen on {host!r}: that is every interface. Name the tailnet or loopback address.")
        raise typer.Exit(code=1)
    else:
        address = host

    store = ReviewStore()
    try:
        store.ensure()
    except ReviewStoreVersionError as refusal:
        _echo(str(refusal))
        raise typer.Exit(code=1) from None

    state = ReviewState(ReviewCatalogue(RUNS_DIR), store)
    state.refresh()
    try:
        server = ReviewHTTPServer((address, port), state)
    except OSError as refusal:
        _echo(f"cannot listen on {address}:{port}: {refusal}")
        raise typer.Exit(code=1) from None

    _echo(f"visual review: {_url(address, port)}")
    if name is not None:
        _echo(f"               {_url(name, port)}")
    _echo(f"watching {RUNS_DIR}")
    _echo(f"notes kept in {store.path}")
    _echo("Ctrl+C stops the server; the notes stay on disk.")
    try:
        serve(server)
    except KeyboardInterrupt:
        _echo("stopped")


@app.command("notes")
def notes_command(
    include_resolved: Annotated[bool, typer.Option("--all", help="Include resolved notes.")] = False,
    as_json: Annotated[bool, typer.Option("--json", help="Print the notes as JSON.")] = False,
    run: Annotated[str, typer.Option("--run", help="Run whose images the notes are compared with.")] = DEFAULT_RUN,
) -> None:
    """Print the review notes left in the browser, by element.

    Each note is compared with the images the run holds now, so a note left
    on an element that has since been re-rendered says so instead of reading
    as a remark about the current images, and a note that pointed at one
    frame says whether that frame is among them.
    """
    store = ReviewStore()
    if not store.exists():
        _echo(f"no review notes yet; `serve` creates {store.path}")
        return
    try:
        notes = store.notes(include_resolved=include_resolved)
    except ReviewStoreVersionError as refusal:
        _echo(str(refusal))
        raise typer.Exit(code=1) from None

    catalogue = ReviewCatalogue(RUNS_DIR, only=run)
    catalogue.refresh()
    view = catalogue.run(run)
    readings = _note_readings(notes, view)

    if as_json:
        payload = [
            {
                **note.model_dump(mode="json"),
                "element_state": str(element_state),
                "frame_state": None if frame_state is None else str(frame_state),
            }
            for note, element_state, frame_state in readings
        ]
        _echo(json.dumps(payload, indent=2, ensure_ascii=False))
        return
    if not readings:
        _echo("no notes" if include_resolved else "no open notes")
        return
    shown_key: str | None = None
    for note, element_state, frame_state in readings:
        shown_key = _print_review_note(note, element_state, frame_state, run, shown_key)


def _print_review_note(
    note: Note, element_state: NoteImageState, frame_state: NoteImageState | None, run: str, shown_key: str | None
) -> str:
    """Print one note and return the last element heading shown."""
    if note.element_key != shown_key:
        shown_key = note.element_key
        _echo("")
        _echo(note.element_key)
    flags = []
    if element_state is NoteImageState.CHANGED:
        flags.append("element re-rendered since")
    elif element_state is NoteImageState.ABSENT:
        flags.append(f"no frame of it in run {run!r}")
    if note.resolved_at is not None:
        flags.append("resolved")
    suffix = f"  [{', '.join(flags)}]" if flags else ""
    _echo(f"  #{note.id} {note.created_at}{suffix}")
    if note.frame_key is not None:
        pointed = ""
        if frame_state is NoteImageState.CHANGED:
            pointed = " (re-rendered since)"
        elif frame_state is NoteImageState.ABSENT:
            pointed = f" (not in run {run!r})"
        _echo(f"    on {note.frame_key}{pointed}")
    for line in note.body.splitlines():
        _echo(f"    {line}")
    return note.element_key


def _write_diff_highlights(
    baseline: str,
    baseline_root: Path,
    candidate_root: Path,
    before: Manifest,
    after: Manifest,
    changed: list[_diff.FrameDiff],
) -> None:
    """Write text differences and pixel highlights for changed frames."""
    destination_root = candidate_root / "diff" / baseline
    frames = {frame.key: frame for frame in after.frames}
    baseline_frames = {frame.key: frame for frame in before.frames}
    written = 0
    for entry in changed:
        stem = entry.key.replace("/", "__")
        if entry.text_diff:
            (destination_root / f"{stem}.diff").parent.mkdir(parents=True, exist_ok=True)
            (destination_root / f"{stem}.diff").write_text(entry.text_diff + "\n", encoding=UTF_8, newline="\n")
        produced = _diff.write_highlight(
            baseline_root / baseline_frames[entry.key].png,
            candidate_root / frames[entry.key].png,
            destination_root / f"{stem}.png",
        )
        written += 1 if produced is not None else 0
    _echo("")
    _echo(f"wrote {written} highlight images to {destination_root}")
