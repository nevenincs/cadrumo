"""Turn the harness's SVG into a PNG a human can look at.

Textual exports SVG, which is exact but awkward to review: file browsers
thumbnail it poorly, contact sheets need raster, and comparing two of them
means comparing markup rather than pixels. So the SVG is parsed back into
the cell grid it describes and repainted with Pillow.

The grid is recovered rather than assumed. Rich writes each run's advertised
``textLength``, so the cell width comes from the document itself and this
renderer does not depend on Rich's font-size-to-advance ratio staying what
it is today. Every glyph is then placed on integer cell boundaries, which is
what keeps box-drawing characters joining up instead of showing hairlines.

The font is the repository's committed Cascadia Mono, pinned by digest for
the same reason the README renderer pins it: a substituted font silently
changes every artefact this tool produces, and box-drawing coverage is
exactly what a fallback font loses first.
"""

from __future__ import annotations

import html
import re
from dataclasses import dataclass
from functools import cache
from hashlib import sha256
from itertools import pairwise
from pathlib import Path
from statistics import median
from typing import Final

from PIL import Image, ImageDraw, ImageFont

from .._paths import REPO_ROOT, UTF_8

FONT_PATH: Final[Path] = REPO_ROOT / "docs" / "_static" / "readme" / "fonts" / "CascadiaMono-Regular.ttf"
FONT_SHA256: Final[str] = "06520d032ec274fa5040b22c6f4a1d829081b24ba40b2da56dae89bf10c7b481"
"""The committed Cascadia Mono. ``dev/readme/render_cli_demo.py`` pins the
same file for the same reason; the dev/tui suite proves the two pins still
name one digest, so a font update cannot land in one and not the other."""

DEFAULT_CELL_HEIGHT: Final[int] = 22
"""Pixel height of one terminal cell at the default scale.

Chosen so an 80-column frame lands near 1000px wide -- large enough to read
a lowercase glyph without zooming, small enough that a 200x50 contact sheet
stays a manageable file."""

_STYLE_RULE = re.compile(r"\.(?P<klass>[\w-]+)\s*\{(?P<body>[^}]*)\}")
_FILL = re.compile(r"fill:\s*(?P<colour>#[0-9a-fA-F]{6})")
_BOLD = re.compile(r"font-weight:\s*bold")
_CHROME = re.compile(r'<rect fill="(?P<colour>#[0-9a-fA-F]{6})"[^>]*rx="\d+"\s*/>')
_TERMINAL_CLIP = re.compile(
    r'<clipPath id="[\w-]*clip-terminal">\s*<rect x="0" y="0"'
    r'\s+width="(?P<width>[\d.]+)"\s+height="(?P<height>[\d.]+)"',
)
_CELL_RECT = re.compile(
    r'<rect fill="(?P<colour>#[0-9a-fA-F]{6})"'
    r'\s+x="(?P<x>[-\d.]+)"\s+y="(?P<y>[-\d.]+)"'
    r'\s+width="(?P<width>[\d.]+)"\s+height="(?P<height>[\d.]+)"'
    r'\s+shape-rendering="crispEdges"\s*/>',
)
_TEXT_RUN = re.compile(
    r'<text class="(?P<klass>[\w-]+)"'
    r'\s+x="(?P<x>[-\d.]+)"\s+y="(?P<y>[-\d.]+)"'
    r'\s+textLength="(?P<length>[\d.]+)"[^>]*>(?P<content>[^<]*)</text>',
)


class RasterError(RuntimeError):
    """The SVG did not describe a terminal grid this renderer understands."""


@dataclass(frozen=True)
class _Run:
    """One horizontal run of text sharing a single style."""

    column: int
    row: int
    text: str
    colour: str
    bold: bool


@dataclass(frozen=True)
class _Band:
    """One background fill covering a whole-cell rectangle."""

    column: int
    row: int
    columns: int
    rows: int
    colour: str


@cache
def _font(pixels: int) -> ImageFont.FreeTypeFont:
    """Load the pinned font at a pixel size, refusing a substituted file."""
    if not FONT_PATH.is_file():
        raise RasterError(f"the pinned raster font is missing: {FONT_PATH}")
    digest = sha256(FONT_PATH.read_bytes()).hexdigest()
    if digest != FONT_SHA256:
        raise RasterError(f"the pinned raster font changed digest: {digest}")
    return ImageFont.truetype(str(FONT_PATH), size=pixels)


_NOTDEF_PROBE: Final[str] = "\ue000"
"""A Private Use Area codepoint no text font assigns a glyph to.

Rendering it yields the font's ``.notdef`` box, which is the reference every
candidate character is compared against."""


@cache
def _notdef_mask(pixels: int) -> bytes:
    """The pinned font's ``.notdef`` bitmap at this size."""
    return bytes(_font(pixels).getmask(_NOTDEF_PROBE))


def _is_missing(font: ImageFont.FreeTypeFont, pixels: int, character: str) -> bool:
    """Whether the pinned font draws ``.notdef`` instead of a real glyph.

    Emptiness is NOT the test. A missing glyph renders as a filled box, so it
    has ink and a bounding box exactly like a real character -- an earlier
    version asked whether the mask was empty and therefore reported that
    nothing was ever missing while a visible tofu sat in the image, which is
    the one direction this field must never fail in. Comparing the rendered
    bitmap against the font's own ``.notdef`` identifies the box for what it
    is.
    """
    return bytes(font.getmask(character)) == _notdef_mask(pixels)


@cache
def _fitted_font(cell_width: int, cell_height: int) -> tuple[ImageFont.FreeTypeFont, int, int]:
    """The largest pinned font whose advance still fits one cell.

    Sized by measurement rather than by a ratio constant: the advance-to-em
    ratio belongs to the font file, so deriving it from the file keeps the
    grid tight if that file is ever replaced by a differently-proportioned
    one. Returns the font and the vertical offset that centres its glyph box
    inside the cell, which is what stops descenders colliding with the row
    below.
    """
    for size in range(cell_height, 3, -1):
        font = _font(size)
        if font.getlength("M") <= cell_width:
            ascent, descent = font.getmetrics()
            return font, max((cell_height - (ascent + descent)) // 2, 0), size
    message = f"no pinned font size fits a {cell_width}x{cell_height} cell"
    raise RasterError(message)


def _style_map(markup: str) -> dict[str, tuple[str, bool]]:
    """Map each generated style class to its fill colour and weight."""
    styles: dict[str, tuple[str, bool]] = {}
    for rule in _STYLE_RULE.finditer(markup):
        fill = _FILL.search(rule["body"])
        if fill is not None:
            styles[rule["klass"]] = (fill["colour"], bool(_BOLD.search(rule["body"])))
    return styles


def _cell_size(markup: str) -> tuple[float, float]:
    """Recover the SVG-unit width and height of one cell.

    Width is the median advertised advance per character across every run,
    which is immune to a single run whose content Rich measured as
    full-width. Height comes from the distance between adjacent baselines.
    """
    advances = [
        float(run["length"]) / len(run["content"])
        for run in _TEXT_RUN.finditer(markup)
        if run["content"] and float(run["length"]) > 0
    ]
    baselines = sorted({float(run["y"]) for run in _TEXT_RUN.finditer(markup)})
    if not advances or len(baselines) < 2:
        raise RasterError("the SVG carries no measurable terminal grid")
    gaps = [round(after - before, 3) for before, after in pairwise(baselines)]
    return median(advances), median(gaps)


_BLOCK_FRACTIONS: Final[dict[str, tuple[float, float, float, float]]] = {
    # character: (left, top, right, bottom) as fractions of one cell.
    "█": (0.0, 0.0, 1.0, 1.0),  # full block
    "▀": (0.0, 0.0, 1.0, 0.5),  # upper half
    "▄": (0.0, 0.5, 1.0, 1.0),  # lower half
    "▌": (0.0, 0.0, 0.5, 1.0),  # left half
    "▐": (0.5, 0.0, 1.0, 1.0),  # right half
    "▁": (0.0, 0.875, 1.0, 1.0),
    "▂": (0.0, 0.75, 1.0, 1.0),
    "▃": (0.0, 0.625, 1.0, 1.0),
    "▅": (0.0, 0.375, 1.0, 1.0),
    "▆": (0.0, 0.25, 1.0, 1.0),
    "▇": (0.0, 0.125, 1.0, 1.0),
    "▉": (0.0, 0.0, 0.875, 1.0),
    "▊": (0.0, 0.0, 0.75, 1.0),
    "▋": (0.0, 0.0, 0.625, 1.0),
    "▍": (0.0, 0.0, 0.375, 1.0),
    "▎": (0.0, 0.0, 0.25, 1.0),
    "▏": (0.0, 0.0, 0.125, 1.0),
    "▕": (0.875, 0.0, 1.0, 1.0),
    "▔": (0.0, 0.0, 1.0, 0.125),
}
"""Block-element characters and the portion of the cell each one fills.

Drawn as rectangles rather than glyphs so adjacent cells tile with no seam.
"""


def _fill_block(
    draw: ImageDraw.ImageDraw,
    column: int,
    row: int,
    cell_width: int,
    cell_height: int,
    fraction: tuple[float, float, float, float],
    colour: str,
) -> None:
    """Paint one block-element cell as exact geometry."""
    left, top, right, bottom = fraction
    x0, y0 = column * cell_width, row * cell_height
    draw.rectangle(
        (
            x0 + round(left * cell_width),
            y0 + round(top * cell_height),
            x0 + round(right * cell_width) - 1,
            y0 + round(bottom * cell_height) - 1,
        ),
        fill=colour,
    )


@dataclass(frozen=True)
class RasterResult:
    """A written PNG, and what the pinned font could not draw into it.

    Missing glyphs are reported rather than substituted. A character the font
    lacks paints as a blank box, and a reviewer who does not know that reads
    the box as a defect in the surface; a reviewer who does know can tell
    "this font lacks it" from "this surface is broken". Substituting a
    lookalike would hide the difference in the other direction.
    """

    path: Path
    missing_glyphs: tuple[str, ...] = ()


def rasterise(svg_path: Path, destination: Path, *, cell_height: int = DEFAULT_CELL_HEIGHT) -> RasterResult:
    """Repaint ``svg_path`` as a PNG at ``destination``."""
    markup = svg_path.read_text(encoding=UTF_8)
    styles = _style_map(markup)
    cell_width_units, cell_height_units = _cell_size(markup)

    terminal = _TERMINAL_CLIP.search(markup)
    if terminal is None:
        raise RasterError("the SVG carries no terminal clip region")

    # Both the background rects and the text runs live inside the translated,
    # clipped content group, so their coordinates are already grid-local and
    # need no origin subtraction. Rich pads a row's top edge and sits its
    # baseline inside the same row, so integer division by the line height
    # lands both on the row they belong to without a per-kind special case.
    # ROUNDED, never floored. A cell origin is an exact multiple of the cell
    # size in principle, but in IEEE floating point 536.8 / 12.2 is
    # 43.99999999999999, so flooring drops it a whole column. The band then
    # lands one column left, leaves the column it should have covered empty,
    # and that empty cell shows the page colour through as a stray block --
    # pale on the light appearance, dark on the dark one. Rounding to the
    # nearest column is exact for every well-formed origin and tolerant of the
    # representation error.
    def _column(x: str) -> int:
        return round(float(x) / cell_width_units)

    def _row(y: str) -> int:
        return int(float(y) // cell_height_units)

    columns = max(round(float(terminal["width"]) / cell_width_units), 1)
    rows = max(round(float(terminal["height"]) / cell_height_units), 1)
    cell_width = max(round(cell_height * cell_width_units / cell_height_units), 1)

    bands = [
        _Band(
            column=_column(rect["x"]),
            row=_row(rect["y"]),
            columns=max(round(float(rect["width"]) / cell_width_units), 1),
            rows=max(round(float(rect["height"]) / cell_height_units), 1),
            colour=rect["colour"],
        )
        for rect in _CELL_RECT.finditer(markup)
    ]
    runs = [
        _Run(
            column=_column(run["x"]),
            row=_row(run["y"]),
            text=html.unescape(run["content"]),
            colour=styles.get(run["klass"], ("#c5c8c6", False))[0],
            bold=styles.get(run["klass"], ("#c5c8c6", False))[1],
        )
        for run in _TEXT_RUN.finditer(markup)
    ]
    if not runs:
        raise RasterError("the SVG carries no text runs")

    # The page colour is the terminal's OWN background, taken as the colour
    # covering the most cells. It is emphatically NOT the `rx`-rounded chrome
    # rect: that is the window frame Rich draws around the screenshot, it is
    # near-black in both appearances, and filling the canvas with it made
    # every cell that carries no explicit background band show through as a
    # dark bar -- which on the light appearance reads as a mystery black
    # element that exists nowhere in the terminal.
    coverage: dict[str, int] = {}
    for band in bands:
        coverage[band.colour] = coverage.get(band.colour, 0) + band.columns * band.rows
    if coverage:
        background = max(coverage.items(), key=lambda entry: entry[1])[0]
    else:
        chrome = _CHROME.search(markup)
        background = chrome["colour"] if chrome is not None else "#000000"

    image = Image.new("RGB", (columns * cell_width, rows * cell_height), background)
    draw = ImageDraw.Draw(image)
    for band in bands:
        draw.rectangle(
            (
                band.column * cell_width,
                band.row * cell_height,
                (band.column + band.columns) * cell_width - 1,
                (band.row + band.rows) * cell_height - 1,
            ),
            fill=band.colour,
        )

    glyph, baseline_offset, glyph_pixels = _fitted_font(cell_width, cell_height)
    missing: set[str] = set()
    for run in runs:
        for offset, character in enumerate(run.text):
            if not character.strip():
                continue

            # Block elements are drawn as geometry, never as glyphs. The font
            # is sized so its ADVANCE fits the cell, which leaves every glyph
            # a little smaller than the cell it occupies -- invisible for
            # letters, and ruinous for the block characters that are supposed
            # to tile seamlessly. Textual draws button edges and scrollbars
            # out of these, so glyph-rendered blocks produced a brick-wall
            # pattern along edges that are solid in a real terminal.
            fraction = _BLOCK_FRACTIONS.get(character)
            if fraction is not None:
                _fill_block(draw, run.column + offset, run.row, cell_width, cell_height, fraction, run.colour)
                continue

            if _is_missing(glyph, glyph_pixels, character):
                missing.add(character)
            position = ((run.column + offset) * cell_width, run.row * cell_height + baseline_offset)
            draw.text(position, character, font=glyph, fill=run.colour)
            if run.bold:
                # The pinned family ships a regular face only, so weight is
                # synthesised the way a terminal without a bold face does it:
                # the glyph again, one pixel across. A stroke outline was the
                # obvious alternative and is wrong at this size -- it thickens
                # every edge including the inside of counters, and turns small
                # text into blobs rather than making it read as heavier.
                draw.text((position[0] + 1, position[1]), character, font=glyph, fill=run.colour)

    destination.parent.mkdir(parents=True, exist_ok=True)
    image.save(destination, optimize=True)
    return RasterResult(path=destination, missing_glyphs=tuple(sorted(missing)))


__all__ = ["DEFAULT_CELL_HEIGHT", "FONT_PATH", "FONT_SHA256", "RasterError", "RasterResult", "rasterise"]
