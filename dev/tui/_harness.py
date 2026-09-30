"""Drive the repository TUI harness as a subprocess.

``dev.tui.harness`` owns surface construction, pilot replay and SVG export.
This module does not reimplement any of it: it runs that harness and collects
what it writes.

Each capture is one fresh process. The harness rebuilds its app from birth on
every command, so a frame is always a statement about the current tree, and
a crash in one surface cannot leave residue that colours the next.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from dev._paths import REPO_ROOT, UTF_8
from dev.packaging.command_execution import run_command

from ._artifacts import FrameFailureKind, SequenceProvenance, ThemeName
from ._viewports import Viewport

HARNESS_MODULE: Final[str] = "dev.tui.harness"
WORKSPACE_ENV_VAR: Final[str] = "CADRUMO_TUI_WORKSPACE"

_ELAPSED = re.compile(r"·\s*(?P<ms>[\d.]+)ms\s")
"""The wall-clock build cost the harness stamps into the frame header."""

_TIMEOUT_SECONDS: Final[int] = 300
"""Generous: a surface that provisions a real encrypted profile pays real
Argon2id derivation on first build, which is slow by design."""

_SCENARIO_TIMEOUT_SECONDS: Final[int] = 3600
"""One scenario runs a documentation sequence and then captures every page at
every requested geometry and appearance in the same process, so it is bounded
by the whole scenario rather than by one frame."""


class HarnessError(RuntimeError):
    """The harness refused or failed, with its own diagnostics attached."""

    def __init__(self, message: str, *, kind: FrameFailureKind = FrameFailureKind.CRASHED) -> None:
        """Record the diagnostics and how the harness failed."""
        super().__init__(message)
        self.kind = kind


def classify(output: str) -> FrameFailureKind:
    """Read the harness's own output to tell a refusal from a crash.

    The harness prints ``refused: <exception>`` from the one place it catches
    an exception, and prints a bare traceback when it dies anywhere else. That
    is the whole signal, and it belongs to the harness's contract rather than
    to a guess made here about which exception types are recoverable.
    """
    for line in output.splitlines():
        stripped = line.strip()
        if stripped.startswith("refused:"):
            return FrameFailureKind.REFUSED
        if stripped.startswith("Traceback (most recent call last)"):
            return FrameFailureKind.CRASHED
    return FrameFailureKind.CRASHED


@dataclass(frozen=True)
class Surface:
    """One drivable surface, as the development harness reports it."""

    name: str
    summary: str
    needs_profile: bool


@dataclass(frozen=True)
class Capture:
    """One rendered frame: the SVG on disk, and the harness's own reading."""

    surface: str
    viewport: Viewport
    theme: ThemeName
    svg_path: Path
    frame_text: str

    @property
    def geometry_findings(self) -> tuple[str, ...]:
        """The harness's advisory appearance readings for this frame.

        Reported, never asserted: the harness prints what it measured and
        this tool carries it to the reviewer, who judges.
        """
        return tuple(
            line.partition("── GEOM:")[2].strip()
            for line in self.frame_text.splitlines()
            if line.startswith("── GEOM:")
        )

    @property
    def elapsed_ms(self) -> float | None:
        """Cost of reaching this frame from a cold app, per the harness header."""
        found = _ELAPSED.search(self.frame_text)
        return float(found["ms"]) if found is not None else None

    @property
    def stable_text(self) -> str:
        """The frame reading with this tool's own non-determinism removed.

        The harness stamps a wall-clock build cost into the frame header, so
        two renders of an unchanged surface never produce identical text and
        a diff would report every frame as changed -- drowning the real
        findings it exists to surface. The number is a performance reading
        rather than an appearance one, so it is lifted into the manifest and
        redacted here. Content the SURFACE makes non-deterministic, such as
        the status page's session deadlines, is deliberately left alone: that
        is the surface behaving that way, and hiding it would be this tool
        editing the evidence.
        """
        return _ELAPSED.sub("· ---ms ", self.frame_text)


def _environment(workspace: str) -> dict[str, str]:
    """A process environment with this run's private harness workspace.

    Concurrent reviewers each need their own session journal and storage
    root; the harness reads this variable to give them one.
    """
    environment = dict(os.environ)
    environment[WORKSPACE_ENV_VAR] = workspace
    environment["PYTHONIOENCODING"] = UTF_8
    return environment


def _run(arguments: tuple[str, ...], *, workspace: str, timeout_seconds: float = _TIMEOUT_SECONDS) -> str:
    """Run one harness command and return its stdout, or raise its refusal."""
    result = run_command(
        [sys.executable, "-m", HARNESS_MODULE, *arguments],
        cwd=REPO_ROOT,
        errors="replace",
        environment=_environment(workspace),
        timeout_seconds=timeout_seconds,
    )
    if result.returncode != 0:
        diagnostics = "\n".join(part.strip() for part in (result.stdout, result.stderr) if part.strip())
        joined = " ".join(arguments)
        raise HarnessError(
            f"harness `{joined}` exited {result.returncode}\n{diagnostics}",
            kind=classify(diagnostics),
        )
    return result.stdout


def surfaces(*, workspace: str = "visual-inventory") -> tuple[Surface, ...]:
    """Ask the harness which surfaces it can drive.

    The list is the harness's, not this tool's. A surface added there shows
    up here with no edit on this side, which is what keeps the two from
    drifting into disagreeing about what exists.
    """
    listing = _run(("surfaces",), workspace=workspace)
    found: list[Surface] = []
    for line in listing.splitlines():
        if not line.strip():
            continue
        name, _, remainder = line.partition(" ")
        summary = remainder.strip()
        needs_profile = summary.endswith("(needs profile)")
        if needs_profile:
            summary = summary.removesuffix("(needs profile)").strip()
        found.append(Surface(name=name, summary=summary, needs_profile=needs_profile))
    if not found:
        raise HarnessError("the harness listed no surfaces")
    return tuple(found)


def coverage(*, workspace: str = "visual-inventory") -> dict[str, tuple[str, ...]]:
    """Ask the harness which interfaces each surface paints at its opening frame.

    The surface registry is the authority. Reading it here rather than keeping
    a second hand-written opinion on this side is what stops the review
    inventory from under-claiming coverage after a fixture lands: a surface
    that declares its interfaces is covered the moment it exists.
    """
    reported: dict[str, tuple[str, ...]] = {}
    for line in _run(("coverage",), workspace=workspace).splitlines():
        name, _, remainder = line.strip().partition(" ")
        if not name or not remainder:
            continue
        reported[name] = tuple(part for part in remainder.split(",") if part)
    return reported


def capture(
    surface: str,
    viewport: Viewport,
    *,
    theme: ThemeName,
    svg_path: Path,
    locale: str | None = None,
    workspace: str = "visual-inventory",
) -> Capture:
    """Open ``surface`` at ``viewport`` and write its SVG to ``svg_path``.

    One harness command: ``open --shot`` prints the frame bands this tool
    carries into the manifest and exports the same settled frame as SVG, so a
    frame costs one interpreter start and one cold build rather than two.
    """
    svg_path.parent.mkdir(parents=True, exist_ok=True)
    opening = ("open", surface, "--size", viewport.label, "--theme", theme, "--shot", str(svg_path))
    frame_text = _run(opening if locale is None else (*opening, "--locale", locale), workspace=workspace)
    if not svg_path.is_file() or svg_path.stat().st_size == 0:
        raise HarnessError(f"the harness wrote no SVG for {surface} at {viewport.label}")
    return Capture(
        surface=surface,
        viewport=viewport,
        theme=theme,
        svg_path=svg_path,
        frame_text=frame_text.rstrip("\n"),
    )


@dataclass(frozen=True)
class Scenario:
    """One sequence-backed scenario, as the development harness reports it."""

    name: str
    summary: str
    pages: dict[str, str]
    """Each page the scenario captures, to the surface name it is reviewed under."""


def scenarios(*, workspace: str = "visual-inventory") -> tuple[Scenario, ...]:
    """Ask the harness which sequence-backed scenarios it can run."""
    listing = json.loads(_run(("sequences",), workspace=workspace))
    return tuple(
        Scenario(name=entry["name"], summary=entry["summary"], pages=dict(entry["pages"])) for entry in listing
    )


def reviewable_surface_names(
    surfaces: tuple[Surface, ...],
    scenarios: tuple[Scenario, ...],
) -> tuple[str, ...]:
    """Every surface a frame can be reviewed under: the harness's, then each scenario page.

    Both kinds are executable -- a surface through ``open``, a scenario page
    through ``sequence`` -- so both are what a coverage row may name.
    """
    return (
        *(surface.name for surface in surfaces),
        *(surface for scenario in scenarios for surface in scenario.pages.values()),
    )


@dataclass(frozen=True)
class ScenarioCapture:
    """One page of a scenario at one geometry and appearance."""

    page: str
    capture: Capture


def capture_scenario(
    name: str,
    viewports: tuple[Viewport, ...],
    *,
    themes: tuple[ThemeName, ...],
    out_dir: Path,
    workspace: str = "visual-inventory",
) -> tuple[SequenceProvenance, tuple[ScenarioCapture, ...]]:
    """Run one scenario's sequence once and collect every page it captured.

    One harness process per scenario, not per frame: the sequence builds its
    declaration through the real CLI chain, and running that again for each
    of dozens of frames would multiply the slowest part of the render for no
    change in what is shown. Each capture inside still builds a fresh app.
    """
    arguments = ["sequence", name, "--out", str(out_dir)]
    for viewport in viewports:
        arguments.extend(("--size", viewport.label))
    for theme in themes:
        arguments.extend(("--theme", str(theme)))
    try:
        output = _run(tuple(arguments), workspace=workspace, timeout_seconds=_SCENARIO_TIMEOUT_SECONDS)
    except subprocess.TimeoutExpired as expired:
        raise HarnessError(f"scenario {name} ran past {expired.timeout:.0f}s and was stopped") from expired
    document = json.loads(output)
    by_label = {viewport.label: viewport for viewport in viewports}
    captures = tuple(
        ScenarioCapture(
            page=entry["page"],
            capture=Capture(
                surface=entry["surface"],
                viewport=by_label[f"{entry['width']}x{entry['height']}"],
                theme=ThemeName(entry["theme"]),
                svg_path=Path(entry["svg"]),
                frame_text=entry["frame"].rstrip("\n"),
            ),
        )
        for entry in document["captures"]
    )
    missing = [item.capture.svg_path.name for item in captures if not item.capture.svg_path.is_file()]
    if missing:
        raise HarnessError(f"scenario {name} reported frames it wrote no SVG for: {', '.join(missing[:5])}")
    return SequenceProvenance.model_validate(document["provenance"]), captures


__all__ = [
    "HARNESS_MODULE",
    "Capture",
    "FrameFailureKind",
    "HarnessError",
    "Scenario",
    "ScenarioCapture",
    "Surface",
    "ThemeName",
    "capture",
    "capture_scenario",
    "classify",
    "coverage",
    "reviewable_surface_names",
    "scenarios",
    "surfaces",
]
