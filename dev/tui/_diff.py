"""Compare two review runs and say what changed.

Two questions get asked of a visual inventory, and they want different
answers. "Did anything move?" is answered by digests, cheaply, across every
frame. "What moved?" needs the frames side by side, and for a terminal the
most legible form is a text diff of the cells plus an image that marks the
rows that differ -- a raw pixel subtraction of two terminal frames lights up
every antialiased glyph edge and shows nothing a reviewer can act on.
"""

from __future__ import annotations

import difflib
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

from PIL import Image, ImageChops

from .._paths import UTF_8
from ._artifacts import Manifest, RenderedFrame


class Change(StrEnum):
    """What happened to one frame between two runs."""

    ADDED = "added"
    REMOVED = "removed"
    CHANGED = "changed"
    UNCHANGED = "unchanged"


@dataclass(frozen=True)
class FrameDiff:
    """One frame's fate across the two runs."""

    key: str
    change: Change
    pixels_differ: bool = False
    text_differ: bool = False
    text_diff: str = ""

    @property
    def notable(self) -> bool:
        """Whether a reviewer needs to look at this entry at all."""
        return self.change is not Change.UNCHANGED


def _by_key(manifest: Manifest) -> dict[str, RenderedFrame]:
    return {frame.key: frame for frame in manifest.frames}


def _text_diff(baseline_root: Path, candidate_root: Path, frame: RenderedFrame, other: RenderedFrame) -> str:
    """A unified diff of the two frames' cell text."""
    before = (baseline_root / frame.text).read_text(encoding=UTF_8).splitlines()
    after = (candidate_root / other.text).read_text(encoding=UTF_8).splitlines()
    return "\n".join(
        difflib.unified_diff(
            before, after, fromfile=f"baseline/{frame.key}", tofile=f"candidate/{other.key}", lineterm=""
        )
    )


def compare(
    baseline_root: Path,
    baseline: Manifest,
    candidate_root: Path,
    candidate: Manifest,
) -> tuple[FrameDiff, ...]:
    """Diff every frame the two runs share, and name the ones they do not."""
    before, after = _by_key(baseline), _by_key(candidate)
    results: list[FrameDiff] = []

    for key in sorted(before.keys() - after.keys()):
        results.append(FrameDiff(key=key, change=Change.REMOVED))
    for key in sorted(after.keys() - before.keys()):
        results.append(FrameDiff(key=key, change=Change.ADDED))

    for key in sorted(before.keys() & after.keys()):
        old, new = before[key], after[key]
        pixels_differ = old.png_sha256 != new.png_sha256
        text_differ = old.text_sha256 != new.text_sha256
        if not pixels_differ and not text_differ:
            results.append(FrameDiff(key=key, change=Change.UNCHANGED))
            continue
        results.append(
            FrameDiff(
                key=key,
                change=Change.CHANGED,
                pixels_differ=pixels_differ,
                text_differ=text_differ,
                text_diff=_text_diff(baseline_root, candidate_root, old, new) if text_differ else "",
            ),
        )
    return tuple(results)


def write_highlight(baseline_png: Path, candidate_png: Path, destination: Path) -> Path | None:
    """Write a side-by-side image with the differing region boxed.

    Returns ``None`` when the two frames are different SHAPES: stacking a
    80x24 frame beside a 120x40 one and calling the result a difference map
    would invent a finding out of a resize the reviewer already knows about.
    """
    before = Image.open(baseline_png).convert("RGB")
    after = Image.open(candidate_png).convert("RGB")
    if before.size != after.size:
        return None

    difference = ImageChops.difference(before, after)
    box = difference.getbbox()

    gap = 16
    canvas = Image.new("RGB", (before.width * 2 + gap, before.height), "#101010")
    canvas.paste(before, (0, 0))
    canvas.paste(after, (before.width + gap, 0))
    if box is not None:
        from PIL import ImageDraw

        draw = ImageDraw.Draw(canvas)
        left, top, right, bottom = box
        for offset in (0, before.width + gap):
            draw.rectangle((left + offset, top, right + offset, bottom), outline="#ff4d4d", width=2)

    destination.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(destination, optimize=True)
    return destination


def render_report(diffs: tuple[FrameDiff, ...]) -> str:
    """A terminal-readable summary of a comparison."""
    notable = [entry for entry in diffs if entry.notable]
    if not notable:
        return f"no change across {len(diffs)} frames"

    lines = [f"{len(notable)} of {len(diffs)} frames changed", ""]
    for entry in notable:
        detail = ""
        if entry.change is Change.CHANGED:
            axes = [name for name, flag in (("pixels", entry.pixels_differ), ("text", entry.text_differ)) if flag]
            detail = f" ({', '.join(axes)})"
        lines.append(f"{entry.change.value:<9} {entry.key}{detail}")
    return "\n".join(lines)


__all__ = ["Change", "FrameDiff", "compare", "render_report", "write_highlight"]
