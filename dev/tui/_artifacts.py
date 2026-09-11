"""The shape of one review run on disk, and the manifest that describes it.

A run is a directory of images plus a manifest. The manifest is what makes
the run comparable: it records, per frame, the digest of the rendered PNG and
of the harness's own text reading, so a later run can be diffed against this
one without re-deriving anything.

Digests cover both because they fail differently. A PNG digest catches every
visible change including one no text reading would show -- a colour, a
border weight, a cell that moved. A text digest catches a change in what the
frame SAYS while pixels happen to hash the same, and stays readable in a
diff, which a PNG digest never is.
"""

from __future__ import annotations

import json
import shutil
from datetime import UTC, datetime
from enum import StrEnum
from hashlib import sha256
from pathlib import Path
from typing import Final

from pydantic import BaseModel, ConfigDict, Field, model_validator

from dev._paths import REPO_ROOT, UTF_8

from ._inventory import InterfaceKind
from ._viewports import VIEWPORTS, Orientation, ViewportName

RUN_ROOT: Final[Path] = REPO_ROOT / ".tmp-tui-visual-inventory"
"""Where runs land. Gitignored: these are review artefacts, never durable."""

RUNS_DIR: Final[Path] = RUN_ROOT / "runs"
"""Every run lives here, one directory each, and nothing else does.

The root used to hold run directories, stray probe images and loose logs side
by side, so a reviewer could not tell the current review from a three-frame
experiment. Runs are now the only thing under `runs/`, throwaway output goes to
`scratch/`, and a run's log lives inside the run it describes.
"""

SCRATCH_DIR: Final[Path] = RUN_ROOT / "scratch"
"""Probe and experiment output. Never a review artefact."""

DEFAULT_RUN_NAME: Final[str] = "current"
"""The canonical review. `runs/current/` is always the one to open.

A stable default is the contract: the reviewer opens one path, not whichever
name the last session happened to invent.
"""

RENDER_LOG_NAME: Final[str] = "render.log"

MANIFEST_NAME: Final[str] = "manifest.json"
MANIFEST_SCHEMA_VERSION: Final[int] = 3
"""Bumped whenever the manifest shape changes. Older runs are refused rather
than upgraded -- see :func:`read_manifest`."""
INDEX_NAME: Final[str] = "index.md"

FRAME_ARTEFACT_KINDS: Final[tuple[str, ...]] = ("png", "svg", "text")
"""The three files one rendered frame writes, and the subdirectories holding
them. Named once because two separate numbers are derived from it: the sweep
walks these directories, and the purge bound below is a count of them."""

MAX_STALE_FILES_PER_PURGE: Final[int] = 24
"""How many unclaimed files one purge may delete before it refuses.

Twenty-four is one surface's full matrix: four viewports times two themes
times the three files a frame writes. A surface that was renamed strands
exactly that many, so the bound admits the ordinary case and refuses the
one that is never ordinary -- a run whose matrix SHRANK, which strands the
frames of every surface it no longer asks for."""


class ThemeName(StrEnum):
    """The appearances a frame may be reviewed under.

    The one definition of the vocabulary. It was previously a bare tuple of
    strings in the command line, checked only where the command line parsed
    its own ``--theme`` option: every record that CARRIED a theme typed it
    ``str``, so a manifest read back from disk, or a frame built by hand,
    could name an appearance that has never been rendered and be reported as
    a reviewed one.

    The values are the renderable subset of the application's own
    :class:`~cadrumo.core.config_support.TuiAppearance`. ``AUTO`` is excluded
    deliberately: it defers the choice to the host terminal, so a frame
    recorded under it would name no appearance at all, and a review has to
    know which one it is looking at. The join to that vocabulary is asserted
    by this package's tests rather than derived here, so the two spellings
    cannot drift apart unnoticed.
    """

    DARK = "dark"
    LIGHT = "light"


class RenderedFrame(BaseModel):
    """One surface rendered at one viewport under one theme."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    surface: str
    viewport: ViewportName
    columns: int
    rows: int
    orientation: Orientation
    theme: ThemeName
    png: str
    svg: str
    text: str
    png_sha256: str
    text_sha256: str
    cell_height: int
    """Pixel height of one terminal cell in THIS frame's PNG.

    Carried per frame rather than once per run because a repaint can
    reach only part of a run: `rasterise` keeps any frame whose SVG has
    gone missing exactly as recorded, so its pixels stay at the height
    they were painted at while the rest move. One run-level number
    cannot say that, and stamping the new one over a mixed run claims a
    resolution the images do not have."""

    elapsed_ms: float | None = None
    """Cold-build cost of this frame, lifted out of the diffed text so a
    timing wobble is not reported as a visual change."""
    geometry_findings: tuple[str, ...] = ()
    missing_glyphs: tuple[str, ...] = ()
    """Characters the pinned raster font could not draw; a blank box in the
    PNG at one of these is a font gap, never a defect in the surface."""

    @model_validator(mode="after")
    def _geometry_matches_the_named_viewport(self) -> RenderedFrame:
        """Refuse a frame whose grid contradicts the viewport it names.

        ``columns``, ``rows`` and ``orientation`` are a SECOND statement of
        what :data:`~dev.tui._viewports.VIEWPORTS` already decides for the
        named viewport, kept in the record so the index reads without
        resolving anything. A second statement with no owner is free to
        disagree with the first, and a manifest saying ``small`` at 200x50
        is a claim that no frame on disk supports.
        """
        shape = VIEWPORTS[self.viewport]
        recorded = (self.columns, self.rows, self.orientation)
        owned = (shape.columns, shape.rows, shape.orientation)
        if recorded != owned:
            message = (
                f"frame {self.surface}/{self.viewport}/{self.theme} records {recorded}, "
                f"but viewport {self.viewport} is {owned}"
            )
            raise ValueError(message)
        return self

    @property
    def key(self) -> str:
        """The identity a diff matches frames on across two runs."""
        return f"{self.surface}/{self.viewport}/{self.theme}"


class InterfaceRecord(BaseModel):
    """One TUI interface class, and whether this run put it on screen."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    qualname: str
    kind: InterfaceKind
    locator: str
    rendered_by: tuple[str, ...] = ()
    note: str = ""

    @property
    def covered(self) -> bool:
        """Whether some rendered surface in this run shows this interface."""
        return bool(self.rendered_by)


class FrameFailureKind(StrEnum):
    """Why a frame is absent from a run, as the manifest records it.

    The one definition of the vocabulary. It was previously spelled three
    times over a field typed ``str``, which accepted all of them and checked
    none: an enum in the harness driver carrying two of the values, a bare
    ``"raster"`` string literal in the command line, and a prose list in the
    field docstring naming all three.
    """

    REFUSED = "refused"
    """An application guard inside the harness said no.

    Raised while BUILDING the app, before a cell is laid out, so neither the
    terminal geometry nor the appearance can change the answer. Re-asking the
    same surface at another size is guaranteed to get the same refusal, which
    is what makes skipping the rest of that surface honest rather than a
    guess."""

    CRASHED = "crashed"
    """The harness process died and printed a raw traceback.

    Nothing caught it, so it is not a considered answer: an import error from
    a half-finished edit in a shared worktree, a killed process, an exhausted
    drive. Frequently transient, so this kind earns a retry and never condemns
    the rest of the surface."""

    RASTER = "raster"
    """The harness produced a frame this tool could not repaint.

    Never retried: the SVG on disk will be identical next time. The failure
    belongs to the rasteriser rather than to the harness, which is why the
    harness never reports this kind and only the manifest carries it."""


class FailedFrame(BaseModel):
    """One frame the harness would not produce, and why."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    surface: str
    viewport: ViewportName
    theme: ThemeName
    kind: FrameFailureKind
    attempts: int = 1
    detail: str = ""

    @property
    def key(self) -> str:
        """The same identity a rendered frame carries."""
        return f"{self.surface}/{self.viewport}/{self.theme}"


class SkippedFrame(BaseModel):
    """One frame not attempted, because its surface had already refused.

    Recorded rather than omitted. A run that simply stops mentioning the
    frames it gave up on is indistinguishable from a run that was never asked
    for them, and the difference is exactly what a reviewer needs to know.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    surface: str
    viewport: ViewportName
    theme: ThemeName
    reason: str

    @property
    def key(self) -> str:
        """The same identity a rendered frame carries."""
        return f"{self.surface}/{self.viewport}/{self.theme}"


class Manifest(BaseModel):
    """Everything one run produced, and everything it did not reach."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: int = MANIFEST_SCHEMA_VERSION
    generated_at: str
    source_revision: str
    """Fingerprint of the rendered source, taken when the run STARTED.

    A full matrix takes about twenty-five minutes and renders each surface in
    its own subprocess, so code landing mid-run splits the output: early frames
    show the old behaviour, late frames the new, and a manifest that records
    only `generated_at` claims all of them equally. That is worse than stale
    frames from an earlier run -- those at least announce themselves as another
    run, while these are all reported as current.
    """
    source_revision_at_end: str
    """The same fingerprint taken when the run FINISHED.

    Equal to `source_revision` on a coherent run. When the two differ the run
    spans an edit and the frames cannot all be trusted, which is what
    `spans_a_source_change` reports and what the writer refuses on.
    """
    cell_height: int
    """The cell height this run was INVOKED with.

    A statement about the request, not about the pixels: each frame
    records the height it was actually painted at. On a coherent run
    every frame agrees with this value, and
    `frames_at_a_foreign_cell_height` reports the ones that do not."""

    frames: tuple[RenderedFrame, ...] = ()
    interfaces: tuple[InterfaceRecord, ...] = ()
    failures: tuple[FailedFrame, ...] = Field(default=())
    """Frames the harness refused or crashed on, kept rather than dropped: a
    run that silently omits what it could not render reads as full coverage."""
    skipped: tuple[SkippedFrame, ...] = Field(default=())
    """Frames deliberately not attempted after their surface refused."""

    @property
    def spans_a_source_change(self) -> bool:
        """Whether the tree changed while this run was rendering."""
        return self.source_revision != self.source_revision_at_end

    @property
    def frames_at_a_foreign_cell_height(self) -> tuple[str, ...]:
        """Frames whose pixels are not at the height this run asked for."""
        return tuple(sorted(frame.key for frame in self.frames if frame.cell_height != self.cell_height))

    @property
    def blocked_surfaces(self) -> tuple[str, ...]:
        """Surfaces that produced no frame at all in this run."""
        rendered = {frame.surface for frame in self.frames}
        attempted = {entry.surface for entry in self.failures} | {entry.surface for entry in self.skipped}
        return tuple(sorted(attempted - rendered))

    @property
    def uncovered(self) -> tuple[InterfaceRecord, ...]:
        """Interfaces this run never painted."""
        return tuple(record for record in self.interfaces if not record.covered)


def source_fingerprint(root: Path | None = None) -> str:
    """A digest of the TUI source the renderer will execute.

    Content-based rather than a git revision: a run is normally started from a
    DIRTY worktree, where `git rev-parse HEAD` is identical before and after an
    edit and so cannot see the change this exists to catch. Hashing the files
    that produce the frames answers the actual question -- is the code that
    rendered frame 1 the code that rendered frame 174.

    Arguments:
        root: Tree to fingerprint. Defaults to the shipped TUI package, which
            is what a render actually executes; injectable so a test can prove
            the fingerprint moves without editing the real worktree, which is
            shared and which a concurrent writer may commit at any moment.
    """
    root = root or Path(__file__).resolve().parents[2] / "src" / "cadrumo" / "entrypoints" / "tui"
    accumulator = sha256()
    for path in sorted(root.rglob("*.py")):
        if "__pycache__" in path.parts:
            continue
        accumulator.update(path.relative_to(root).as_posix().encode(UTF_8))
        accumulator.update(path.read_bytes())
    return accumulator.hexdigest()


def digest(path: Path) -> str:
    """The SHA-256 of a file's bytes."""
    return sha256(path.read_bytes()).hexdigest()


def now() -> str:
    """An ISO-8601 UTC stamp for the manifest header."""
    return datetime.now(UTC).isoformat(timespec="seconds")


def run_directory(name: str) -> Path:
    """The directory a run by this name occupies."""
    return RUNS_DIR / name


def known_runs() -> tuple[Path, ...]:
    """Every run directory that currently holds a manifest."""
    if not RUNS_DIR.is_dir():
        return ()
    return tuple(sorted(p for p in RUNS_DIR.iterdir() if (p / MANIFEST_NAME).is_file()))


def write_manifest(directory: Path, manifest: Manifest) -> Path:
    """Persist ``manifest`` into ``directory`` and return its path."""
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / MANIFEST_NAME
    path.write_text(manifest.model_dump_json(indent=2) + "\n", encoding=UTF_8, newline="\n")
    return path


def stale_artifacts(directory: Path, manifest: Manifest) -> tuple[Path, ...]:
    """Files in a run directory that this run's manifest does not claim.

    A run writes into a directory it may share with an earlier one, so frames
    from a previous render survive beside the current set with nothing marking
    them. A reviewer opening the directory cannot tell which is which, and a
    surface can be signed off as it looked two code changes ago -- the inverse
    of the silent absence `unaccounted_frames` catches, and just as misleading.
    """
    claimed = {(directory / name).resolve() for frame in manifest.frames for name in (frame.png, frame.svg, frame.text)}
    found: list[Path] = []
    for kind in FRAME_ARTEFACT_KINDS:
        sub = directory / kind
        if not sub.is_dir():
            continue
        found.extend(path for path in sorted(sub.iterdir()) if path.is_file() and path.resolve() not in claimed)
    return tuple(found)


def missing_artifacts(directory: Path, manifest: Manifest) -> tuple[str, ...]:
    """Files this run's manifest names that the directory does not hold.

    The inverse walk of :func:`stale_artifacts`, and the one nothing else
    performs. The sweep asks which files the manifest fails to claim; this
    asks which claims fail to find a file, and the two go wrong for
    different reasons. A claim outlives its file whenever a removal and the
    record of it are undone separately: `purge_stale_artifacts` skips a path
    that vanished under it, `commit_staged_run` leaves a two-call window in
    which a snapshot is gone and its replacement not yet in place, and
    `rasterise` deliberately keeps the record of a frame whose SVG has
    disappeared. Each is correct on its own; each can leave the manifest
    asserting bytes that are not there.

    Nothing surfaced it, because the manifest is the only thing anyone
    reads: the index links a PNG that 404s, and :func:`_diff.compare` opens
    the recorded text path directly and dies with a `FileNotFoundError`
    naming a file rather than a run.

    Returns:
        The manifest-relative names, sorted, that no file backs.
    """
    named = sorted(
        {name for frame in manifest.frames for name in (frame.png, frame.svg, frame.text)},
    )
    return tuple(name for name in named if not (directory / name).is_file())


def purge_stale_artifacts(
    directory: Path,
    manifest: Manifest,
    *,
    removal_allowance: int | None = None,
) -> tuple[Path, ...]:
    """Delete the frames this run did not produce, and report what went.

    Deliberately narrow: only regular files under the three frame directories
    of THIS run, only those the manifest does not name. The manifest, index and
    log are never touched, and nothing outside the run directory is considered.

    Narrow is not the same as bounded. Membership in the manifest answers
    "did this run name that file", and the question that decides whether the
    delete is safe is "does this run have a replacement for it" -- the same
    property for a re-rendered frame, a different one for a frame this run was
    never asked to render. The bound is what keeps the second case reviewable;
    see :class:`StaleArtifactPurgeRefusedError`.

    Args:
        directory: The run directory to sweep.
        manifest: The manifest this run is about to write.
        removal_allowance: Files this purge may delete. Defaults to
            :data:`MAX_STALE_FILES_PER_PURGE`. Pass a larger value to
            authorise a deliberate bulk retirement.

    Returns:
        The paths that were actually unlinked, in sorted order.

    Raises:
        StaleArtifactPurgeRefusedError: The sweep found more unclaimed files
            than *removal_allowance* permits. Nothing is removed.
    """
    allowance = MAX_STALE_FILES_PER_PURGE if removal_allowance is None else removal_allowance
    doomed = stale_artifacts(directory, manifest)
    if len(doomed) > allowance:
        listed = ", ".join(path.name for path in doomed[:10])
        raise StaleArtifactPurgeRefusedError(
            f"the sweep would delete {len(doomed)} unclaimed file(s) from {directory}, over the declared bound "
            f"of {allowance}. Nothing was removed. A sweep this size means the run rendered a SMALLER matrix "
            "than the one already on disk, so what it would delete is the frames of surfaces it never asked "
            "for, not residue it replaced; re-render the full matrix, or pass removal_allowance to authorise "
            f"the retirement explicitly. First removals: {listed}"
        )

    removed: list[Path] = []
    for path in doomed:
        # Re-checked rather than trusted, as the sibling prunes under dev/docs
        # do: the listing and the unlink are separate passes, and this one runs
        # at the end of a render measured in tens of minutes. A frame that goes
        # away in between is a benign race, and an unguarded unlink turns it
        # into a FileNotFoundError that would have taken the whole run with it.
        if path.exists():
            path.unlink()
            removed.append(path)
    return tuple(removed)


def snapshot_staging_directory(destination: Path) -> Path:
    """Where a snapshot is assembled before it replaces ``destination``.

    Under ``scratch/`` rather than beside the runs on purpose: a staged copy
    carries a manifest, so parked inside ``runs/`` it would satisfy
    :func:`known_runs` and a reviewer would find a half-built directory
    listed as a review.

    Derived from ``destination`` rather than read off :data:`SCRATCH_DIR`,
    because the swap in :func:`commit_staged_run` is a rename and a rename
    cannot cross a filesystem. A fixed constant put the staged copy on
    whichever drive the repository sits on while the destination was
    somewhere else entirely, and the swap failed with WinError 17.
    """
    return destination.parent.parent / SCRATCH_DIR.name / f"snapshot-{destination.name}"


def stage_run_copy(source: Path, staging: Path) -> Path:
    """Copy ``source`` into ``staging``, discarding any earlier attempt.

    The removal here destroys only a PREVIOUS staging directory, which by
    construction is the residue of a copy that did not finish and is
    therefore never the only copy of anything.
    """
    if staging.exists():
        shutil.rmtree(staging)
    staging.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(source, staging)
    return staging


def commit_staged_run(staging: Path, destination: Path) -> Path:
    """Swap a fully staged copy into ``destination``.

    Split from :func:`stage_run_copy` so the irreversible removal of an
    existing snapshot happens AFTER its replacement is complete on disk,
    not before that replacement is begun. Removing first meant a copy that
    failed part way -- a run is hundreds of files -- left the named
    snapshot destroyed and replaced by a partial tree that still carried a
    manifest, so :func:`known_runs` went on listing it as a review.

    The window this leaves is two calls wide: a failure between the removal
    and the rename leaves ``destination`` absent and the complete copy
    parked at ``staging``. That state is recoverable by hand and, because
    the source run is never touched, by running the snapshot again.
    """
    if destination.exists():
        shutil.rmtree(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    staging.replace(destination)
    return destination


def unaccounted_frames(
    manifest: Manifest,
    *,
    surfaces: tuple[str, ...],
    viewports: tuple[str, ...],
    themes: tuple[str, ...],
) -> tuple[str, ...]:
    """Return every requested frame the manifest neither rendered nor explained.

    A run accounts for a frame in exactly one of three ways: it rendered it, it
    recorded the refusal or crash, or it recorded that it did not attempt it
    behind an earlier refusal. Anything outside those three is a SILENT
    absence, and a reviewer reading the index has no way to tell it apart from
    a surface that was never asked for.
    """
    accounted = {frame.key for frame in manifest.frames}
    accounted |= {frame.key for frame in manifest.failures}
    accounted |= {frame.key for frame in manifest.skipped}
    requested = {f"{surface}/{viewport}/{theme}" for surface in surfaces for viewport in viewports for theme in themes}
    return tuple(sorted(requested - accounted))


class ManifestVersionError(RuntimeError):
    """The manifest on disk was written by a different version of this tool."""


class StaleArtifactPurgeRefusedError(RuntimeError):
    """Raised when one purge would delete more unclaimed files than its bound.

    The purge deletes what THIS run's manifest does not name, which is the
    right question for a frame a re-render replaced and the wrong one for a
    frame it never asked for. A run narrowed with ``--surface`` names a
    fraction of the matrix, so every other surface's frames are unclaimed by
    construction, and a directory that cost about twenty-five minutes to fill
    empties down to the one surface that was re-rendered. Nothing warns: the
    files are gitignored, so there is no diff and no git recovery.

    Bounding it turns that into a reviewable claim. A prune over the bound is
    reported by name and NOTHING is removed, so a run that meant to re-render
    one surface keeps the rest and can say so explicitly through
    ``removal_allowance`` when the retirement is deliberate.
    """


_MANIFEST_ENTRY_MODELS: Final[dict[str, type[BaseModel]]] = {
    "frames": RenderedFrame,
    "interfaces": InterfaceRecord,
    "failures": FailedFrame,
    "skipped": SkippedFrame,
}
"""Every collection ``Manifest`` holds, and the model each entry must match."""


def _defaulted_fields(model: type[BaseModel]) -> frozenset[str]:
    """Field names a current manifest carries but pydantic would supply anyway.

    ``model_dump_json`` emits every field, so a manifest this tool wrote
    declares all of them. A manifest an OLDER shape wrote declares only the
    fields that shape had, and the two cases part here. Omit a REQUIRED
    field and validation refuses, loudly, on its own. Omit a field added
    since with a DEFAULT and pydantic supplies the value in silence -- so
    nothing breaks, nothing makes the author bump
    :data:`MANIFEST_SCHEMA_VERSION`, and every stale run on disk then reads
    as current. That is the one shape change a version integer cannot see,
    and the only one this walk has to answer for.
    """
    return frozenset(name for name, field in model.model_fields.items() if not field.is_required())


def _shape_refusal(payload: dict[str, object]) -> str | None:
    """Why this payload was written by a foreign manifest shape, or ``None``.

    Reports only DEFAULTED fields the payload omits. An unexpected field is
    already refused by ``extra="forbid"`` on every model here, and a missing
    required one by validation; both name the offending field, so repeating
    either check would add nothing.
    """
    checks: list[tuple[str, frozenset[str], object]] = [
        ("manifest", _defaulted_fields(Manifest), payload),
    ]
    for field, model in _MANIFEST_ENTRY_MODELS.items():
        entries = payload.get(field)
        if isinstance(entries, list):
            expected = _defaulted_fields(model)
            checks.extend((f"{field}[{index}]", expected, entry) for index, entry in enumerate(entries))
    for where, expected, entry in checks:
        if not isinstance(entry, dict):
            continue
        absent = sorted(expected - set(entry))
        if absent:
            return f"{where} declares no {', '.join(absent)}"
    return None


def read_manifest(directory: Path) -> Manifest:
    """Load the manifest a previous run wrote into ``directory``.

    A manifest from an older schema is REFUSED, never upgraded. A run is a
    gitignored pile of review artefacts that is cheap to regenerate and
    durable to nobody, so an upgrader here would be migration code defending
    data that should simply be re-rendered. The refusal names the versions and
    says what to do, which is the part a raw validation traceback does not.
    """
    path = directory / MANIFEST_NAME
    if not path.is_file():
        message = f"no manifest in {directory}; is that a render run?"
        raise FileNotFoundError(message)

    payload = json.loads(path.read_text(encoding=UTF_8))
    found = payload.get("schema_version")
    if found != MANIFEST_SCHEMA_VERSION:
        message = (
            f"run {directory.name!r} carries manifest schema {found!r}, "
            f"but this tool writes {MANIFEST_SCHEMA_VERSION}. "
            f"Review runs are disposable: re-render it with "
            f"`python -m dev.tui render --run {directory.name}`."
        )
        raise ManifestVersionError(message)

    foreign = _shape_refusal(payload)
    if foreign is not None:
        message = (
            f"run {directory.name!r} carries manifest schema {MANIFEST_SCHEMA_VERSION}, "
            f"but was written by a different shape of it: {foreign}. "
            f"Review runs are disposable: re-render it with "
            f"`python -m dev.tui render --run {directory.name}`."
        )
        raise ManifestVersionError(message)
    return Manifest.model_validate(payload)


def _index_header(manifest: Manifest) -> str:
    """The index banner, naming a mixed repaint rather than averaging it away."""
    foreign = manifest.frames_at_a_foreign_cell_height
    height = f"cell height {manifest.cell_height}px"
    if foreign:
        painted = sorted({frame.cell_height for frame in manifest.frames})
        height = (
            f"cell height {manifest.cell_height}px requested; frames painted at "
            + "px, ".join(str(value) for value in painted)
            + f"px ({len(foreign)} frame(s) not at the requested height)"
        )
    return f"Generated {manifest.generated_at} · {height}"


def write_index(directory: Path, manifest: Manifest) -> Path:
    """Write the human review index: what to look at, and what is missing."""
    lines = [
        "# TUI visual inventory",
        "",
        _index_header(manifest),
        "",
        "## Frames",
        "",
    ]
    for surface in sorted({frame.surface for frame in manifest.frames}):
        lines.append(f"### {surface}")
        lines.append("")
        for frame in manifest.frames:
            if frame.surface != surface:
                continue
            shape = f"{frame.columns}x{frame.rows} {frame.orientation}"
            lines.append(f"- `{frame.viewport}` {shape} · {frame.theme} — [{frame.png}]({frame.png})")
            for finding in frame.geometry_findings:
                lines.append(f"  - geometry: {finding}")
        lines.append("")

    if manifest.blocked_surfaces:
        lines.extend(("## Surfaces that produced no frame", ""))
        lines.extend(f"- `{name}`" for name in manifest.blocked_surfaces)
        lines.append("")

    if manifest.failures:
        lines.extend(("## Refused", ""))
        for failure in manifest.failures:
            attempts = f" after {failure.attempts} attempts" if failure.attempts > 1 else ""
            lines.append(f"- `{failure.key}` — {failure.kind}{attempts}")
            if failure.detail:
                # Indented as a fenced block: harness diagnostics are several
                # lines of traceback or refusal text, and pasted raw they
                # dissolve the surrounding list into unreadable prose.
                lines.append("  ```")
                lines.extend(f"  {line}" for line in failure.detail.splitlines())
                lines.append("  ```")
        lines.append("")

    if manifest.skipped:
        lines.extend(("## Not attempted", ""))
        lines.extend(f"- `{entry.key}` — {entry.reason}" for entry in manifest.skipped)
        lines.append("")

    lines.extend(("## Interface coverage", ""))
    for record in manifest.interfaces:
        mark = ", ".join(record.rendered_by) if record.covered else "NOT RENDERED"
        suffix = f" — {record.note}" if record.note else ""
        lines.append(f"- `{record.qualname}` ({record.kind}) — {mark}{suffix}")
    lines.append("")

    path = directory / INDEX_NAME
    path.write_text("\n".join(lines), encoding=UTF_8, newline="\n")
    return path


__all__ = [
    "DEFAULT_RUN_NAME",
    "FRAME_ARTEFACT_KINDS",
    "INDEX_NAME",
    "MANIFEST_NAME",
    "MANIFEST_SCHEMA_VERSION",
    "MAX_STALE_FILES_PER_PURGE",
    "RENDER_LOG_NAME",
    "RUNS_DIR",
    "RUN_ROOT",
    "SCRATCH_DIR",
    "FailedFrame",
    "FrameFailureKind",
    "InterfaceKind",
    "InterfaceRecord",
    "Manifest",
    "ManifestVersionError",
    "RenderedFrame",
    "SkippedFrame",
    "StaleArtifactPurgeRefusedError",
    "ThemeName",
    "commit_staged_run",
    "digest",
    "known_runs",
    "missing_artifacts",
    "now",
    "purge_stale_artifacts",
    "read_manifest",
    "run_directory",
    "snapshot_staging_directory",
    "stage_run_copy",
    "stale_artifacts",
    "unaccounted_frames",
    "write_index",
    "write_manifest",
]
