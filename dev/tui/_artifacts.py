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
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path
from typing import Final

from pydantic import BaseModel, ConfigDict, Field

from .._paths import REPO_ROOT, UTF_8

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
MANIFEST_SCHEMA_VERSION: Final[int] = 2
"""Bumped whenever the manifest shape changes. Older runs are refused rather
than upgraded -- see :func:`read_manifest`."""
INDEX_NAME: Final[str] = "index.md"


class RenderedFrame(BaseModel):
    """One surface rendered at one viewport under one theme."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    surface: str
    viewport: str
    columns: int
    rows: int
    orientation: str
    theme: str
    png: str
    svg: str
    text: str
    png_sha256: str
    text_sha256: str
    elapsed_ms: float | None = None
    """Cold-build cost of this frame, lifted out of the diffed text so a
    timing wobble is not reported as a visual change."""
    geometry_findings: tuple[str, ...] = ()
    missing_glyphs: tuple[str, ...] = ()
    """Characters the pinned raster font could not draw; a blank box in the
    PNG at one of these is a font gap, never a defect in the surface."""

    @property
    def key(self) -> str:
        """The identity a diff matches frames on across two runs."""
        return f"{self.surface}/{self.viewport}/{self.theme}"


class InterfaceRecord(BaseModel):
    """One TUI interface class, and whether this run put it on screen."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    qualname: str
    kind: str
    locator: str
    rendered_by: tuple[str, ...] = ()
    note: str = ""

    @property
    def covered(self) -> bool:
        """Whether some rendered surface in this run shows this interface."""
        return bool(self.rendered_by)


class FailedFrame(BaseModel):
    """One frame the harness would not produce, and why."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    surface: str
    viewport: str
    theme: str
    kind: str
    """``refused`` for an application guard, ``crashed`` for a dead process,
    ``raster`` when the frame rendered but could not be repainted."""
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
    viewport: str
    theme: str
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
    path.write_text(manifest.model_dump_json(indent=2) + "\n", encoding=UTF_8)
    return path


def stale_artifacts(directory: Path, manifest: Manifest) -> tuple[Path, ...]:
    """Files in a run directory that this run's manifest does not claim.

    A run writes into a directory it may share with an earlier one, so frames
    from a previous render survive beside the current set with nothing marking
    them. A reviewer opening the directory cannot tell which is which, and a
    surface can be signed off as it looked two code changes ago -- the inverse
    of the silent absence `unaccounted_frames` catches, and just as misleading.
    """
    claimed = {
        (directory / name).resolve()
        for frame in manifest.frames
        for name in (frame.png, frame.svg, frame.text)
    }
    found: list[Path] = []
    for kind in ("png", "svg", "text"):
        sub = directory / kind
        if not sub.is_dir():
            continue
        found.extend(path for path in sorted(sub.iterdir()) if path.is_file() and path.resolve() not in claimed)
    return tuple(found)


def purge_stale_artifacts(directory: Path, manifest: Manifest) -> tuple[Path, ...]:
    """Delete the frames this run did not produce, and report what went.

    Deliberately narrow: only regular files under the three frame directories
    of THIS run, only those the manifest does not name. The manifest, index and
    log are never touched, and nothing outside the run directory is considered.
    """
    removed = stale_artifacts(directory, manifest)
    for path in removed:
        path.unlink()
    return removed


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
    return Manifest.model_validate(payload)


def write_index(directory: Path, manifest: Manifest) -> Path:
    """Write the human review index: what to look at, and what is missing."""
    lines = [
        "# TUI visual inventory",
        "",
        f"Generated {manifest.generated_at} · cell height {manifest.cell_height}px",
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
    path.write_text("\n".join(lines), encoding=UTF_8)
    return path


__all__ = [
    "DEFAULT_RUN_NAME",
    "INDEX_NAME",
    "MANIFEST_NAME",
    "MANIFEST_SCHEMA_VERSION",
    "RENDER_LOG_NAME",
    "RUNS_DIR",
    "RUN_ROOT",
    "SCRATCH_DIR",
    "FailedFrame",
    "InterfaceRecord",
    "Manifest",
    "ManifestVersionError",
    "RenderedFrame",
    "SkippedFrame",
    "digest",
    "known_runs",
    "now",
    "purge_stale_artifacts",
    "read_manifest",
    "run_directory",
    "stale_artifacts",
    "unaccounted_frames",
    "write_index",
    "write_manifest",
]
