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

MANIFEST_NAME: Final[str] = "manifest.json"
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

    schema_version: int = 2
    generated_at: str
    cell_height: int
    frames: tuple[RenderedFrame, ...] = ()
    interfaces: tuple[InterfaceRecord, ...] = ()
    failures: tuple[FailedFrame, ...] = Field(default=())
    """Frames the harness refused or crashed on, kept rather than dropped: a
    run that silently omits what it could not render reads as full coverage."""
    skipped: tuple[SkippedFrame, ...] = Field(default=())
    """Frames deliberately not attempted after their surface refused."""

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


def digest(path: Path) -> str:
    """The SHA-256 of a file's bytes."""
    return sha256(path.read_bytes()).hexdigest()


def now() -> str:
    """An ISO-8601 UTC stamp for the manifest header."""
    return datetime.now(UTC).isoformat(timespec="seconds")


def run_directory(name: str) -> Path:
    """The directory a run by this name occupies."""
    return RUN_ROOT / name


def write_manifest(directory: Path, manifest: Manifest) -> Path:
    """Persist ``manifest`` into ``directory`` and return its path."""
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / MANIFEST_NAME
    path.write_text(manifest.model_dump_json(indent=2) + "\n", encoding=UTF_8)
    return path


def read_manifest(directory: Path) -> Manifest:
    """Load the manifest a previous run wrote into ``directory``."""
    path = directory / MANIFEST_NAME
    if not path.is_file():
        message = f"no manifest in {directory}; is that a render run?"
        raise FileNotFoundError(message)
    return Manifest.model_validate(json.loads(path.read_text(encoding=UTF_8)))


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
                lines.append(f"  - {failure.detail}")
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
    "INDEX_NAME",
    "MANIFEST_NAME",
    "RUN_ROOT",
    "InterfaceRecord",
    "Manifest",
    "RenderedFrame",
    "digest",
    "now",
    "read_manifest",
    "run_directory",
    "write_index",
    "write_manifest",
]
