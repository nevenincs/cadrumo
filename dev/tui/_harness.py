"""Drive the in-boundary TUI devtool harness as a subprocess.

``cadrumo.entrypoints.tui.devtools`` already owns surface construction,
pilot replay and SVG export, and the architecture decision places that
tooling there deliberately. This module does not reimplement any of it: it
runs that harness and collects what it writes, which is the one external
reference the decision sanctions.

Each capture is a fresh process. The harness rebuilds its app from birth on
every command, so a frame is always a statement about the current tree, and
a crash in one surface cannot leave residue that colours the next.
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Final

from .._paths import REPO_ROOT, UTF_8
from ._viewports import Viewport

HARNESS_MODULE: Final[str] = "cadrumo.entrypoints.tui.devtools"
WORKSPACE_ENV_VAR: Final[str] = "CADRUMO_TUI_WORKSPACE"

_ELAPSED = re.compile(r"·\s*(?P<ms>[\d.]+)ms\s")
"""The wall-clock build cost the harness stamps into the frame header."""

_TIMEOUT_SECONDS: Final[int] = 300
"""Generous: a surface that provisions a real encrypted profile pays real
Argon2id derivation on first build, which is slow by design."""


class FailureKind(StrEnum):
    """Why a harness command did not produce a frame.

    The two are handled differently because they fail differently, and the
    harness itself already distinguishes them in its output.
    """

    REFUSED = "refused"
    """The harness caught the exception and reported it as a refusal.

    An application-level guard said no -- an unmet profile-readiness rule, a
    surface that cannot provision its fixture. These are raised while BUILDING
    the app, before a single cell is laid out, so the terminal geometry and
    the appearance cannot change the answer. Re-asking at another size is
    guaranteed to get the same refusal, which is what makes skipping the rest
    of that surface honest rather than a guess."""

    CRASHED = "crashed"
    """The harness process died and printed a raw traceback.

    Nothing caught this, so it is not a considered refusal: an import error
    from a half-finished edit in a shared worktree, a killed process, an
    exhausted drive. Those are frequently transient, so this kind earns a
    retry and never condemns the rest of the surface."""


class HarnessError(RuntimeError):
    """The harness refused or failed, with its own diagnostics attached."""

    def __init__(self, message: str, *, kind: FailureKind = FailureKind.CRASHED) -> None:
        """Record the diagnostics and how the harness failed."""
        super().__init__(message)
        self.kind = kind


def classify(output: str) -> FailureKind:
    """Read the harness's own output to tell a refusal from a crash.

    The harness prints ``refused: <exception>`` from the one place it catches
    an exception, and prints a bare traceback when it dies anywhere else. That
    is the whole signal, and it belongs to the harness's contract rather than
    to a guess made here about which exception types are recoverable.
    """
    for line in output.splitlines():
        stripped = line.strip()
        if stripped.startswith("refused:"):
            return FailureKind.REFUSED
        if stripped.startswith("Traceback (most recent call last)"):
            return FailureKind.CRASHED
    return FailureKind.CRASHED


@dataclass(frozen=True)
class Surface:
    """One drivable surface, as the in-boundary harness reports it."""

    name: str
    summary: str
    needs_profile: bool


@dataclass(frozen=True)
class Capture:
    """One rendered frame: the SVG on disk, and the harness's own reading."""

    surface: str
    viewport: Viewport
    theme: str
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


def _run(arguments: tuple[str, ...], *, workspace: str) -> str:
    """Run one harness command and return its stdout, or raise its refusal."""
    result = subprocess.run(  # noqa: S603 - module and arguments are developer-owned constants
        [sys.executable, "-m", HARNESS_MODULE, *arguments],
        cwd=REPO_ROOT,
        env=_environment(workspace),
        capture_output=True,
        text=True,
        encoding=UTF_8,
        errors="replace",
        timeout=_TIMEOUT_SECONDS,
        check=False,
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
    theme: str,
    svg_path: Path,
    locale: str | None = None,
    workspace: str = "visual-inventory",
) -> Capture:
    """Open ``surface`` at ``viewport`` and write its SVG to ``svg_path``.

    Two harness commands, not one: ``open`` starts the session and prints the
    frame bands this tool carries into the manifest, and ``shot`` exports the
    same settled frame as SVG.
    """
    svg_path.parent.mkdir(parents=True, exist_ok=True)
    opening = ("open", surface, "--size", viewport.label, "--theme", theme)
    frame_text = _run(opening if locale is None else (*opening, "--locale", locale), workspace=workspace)
    _run(("shot", "--out", str(svg_path)), workspace=workspace)
    if not svg_path.is_file() or svg_path.stat().st_size == 0:
        raise HarnessError(f"the harness wrote no SVG for {surface} at {viewport.label}")
    return Capture(
        surface=surface,
        viewport=viewport,
        theme=theme,
        svg_path=svg_path,
        frame_text=frame_text.rstrip("\n"),
    )


__all__ = [
    "HARNESS_MODULE",
    "Capture",
    "FailureKind",
    "HarnessError",
    "Surface",
    "capture",
    "classify",
    "coverage",
    "surfaces",
]
