"""Render the README's light-theme CLI GIF from a real Modelo 115 run.

Run from the repository root with
``uv run --no-sync python dev/readme/render_cli_demo.py``.
"""

from __future__ import annotations

import subprocess
import sys
import textwrap
from functools import cache
from hashlib import sha256
from typing import Final

from PIL import Image, ImageDraw, ImageFont

from cadrumo.application.filing import build_runtime_schema_provider
from cadrumo.core import Period
from cadrumo.domain.calculations.registry.export_parse import parse_export_payload

from .._paths import UTF_8
from .prepare_cli_demo import DEMO_ROOT, REPO_ROOT, demo_environment, prepare_demo

_UTF_8: Final[str] = UTF_8

OUTPUT_PATH = REPO_ROOT / "docs" / "_static" / "readme" / "cli-demo.gif"
FONT_PATH = REPO_ROOT / "docs" / "_static" / "readme" / "fonts" / "CascadiaMono-Regular.ttf"
FICHERO_PATH = DEMO_ROOT / "m115.boe"
DISPLAY_COMMAND = (
    "aeat app quickfile --modelo=115 --year=2026 --period=1T --casilla=04=0 --output=var/readme-demo/m115.boe"
)
_CLI_BOOTSTRAP = "from cadrumo.entrypoints.cli import main; main()"
_CLI_ARGUMENTS = (
    "app",
    "quickfile",
    "--modelo=115",
    "--year=2026",
    "--period=1T",
    "--casilla=04=0",
    "--output=var/readme-demo/m115.boe",
)
_VISIBLE_FIELDS = frozenset(
    {
        "operation",
        "modelo",
        "filing_year",
        "period",
        "registry_revision_id",
        "stage",
        "completed",
        "output_path",
        "file_sha256",
    },
)

_WIDTH = 1100
_HEIGHT = 650
_BACKGROUND = "#E9E3DA"
_TERMINAL = "#FCFBF8"
_BORDER = "#D7CEC1"
_TEXT = "#2B302D"
_MUTED = "#6B706C"
_CORAL = "#C9573F"
_GREEN = "#568A73"
_YELLOW = "#B6812C"
_FONT_SHA256 = "06520d032ec274fa5040b22c6f4a1d829081b24ba40b2da56dae89bf10c7b481"


def _run_quickfile() -> tuple[str, ...]:
    """Run the production CLI and return the stable, reader-relevant output rows."""
    result = subprocess.run(  # noqa: S603 - executable and arguments are developer-owned constants
        [sys.executable, "-c", _CLI_BOOTSTRAP, *_CLI_ARGUMENTS],
        cwd=REPO_ROOT,
        env=demo_environment(),
        capture_output=True,
        text=True,
        encoding=_UTF_8,
        errors="replace",
        timeout=180,
        check=False,
    )
    if result.returncode != 0:
        diagnostics = "\n".join(part.strip() for part in (result.stdout, result.stderr) if part.strip())
        raise RuntimeError(f"quickfile failed with exit code {result.returncode}\n{diagnostics}")
    rows = tuple(line for line in result.stdout.splitlines() if line.partition("\t")[0] in _VISIBLE_FIELDS)
    fields: dict[str, list[tuple[str, ...]]] = {}
    for row in rows:
        parts = tuple(row.split("\t"))
        fields.setdefault(parts[0], []).append(parts[1:])
    expected_scalars = {
        "operation": ("quickfile",),
        "modelo": ("115",),
        "filing_year": ("2026",),
        "period": ("1T",),
        "registry_revision_id": ("2019-y-siguientes",),
        "completed": ("true",),
    }
    for field, expected in expected_scalars.items():
        if fields.get(field) != [expected]:
            raise RuntimeError(f"quickfile {field} drifted: expected {[expected]}, got {fields.get(field)}")
    expected_stages = ("readiness", "create", "calculate", "verify", "export")
    actual_stages = tuple(stage[0] for stage in fields.get("stage", ()))
    if actual_stages != expected_stages:
        raise RuntimeError(f"quickfile stages drifted: expected {expected_stages}, got {actual_stages}")
    for stage in fields["stage"]:
        if stage[0] in {"create", "calculate", "verify", "export"} and stage[1] != "ok":
            raise RuntimeError(f"quickfile stage did not succeed: {stage}")
    if not FICHERO_PATH.is_file() or FICHERO_PATH.stat().st_size == 0:
        raise RuntimeError(f"quickfile did not write a non-empty fichero: {FICHERO_PATH}")
    payload = FICHERO_PATH.read_bytes()
    reported_hash = fields.get("file_sha256", [("",)])[0][0]
    actual_hash = sha256(payload).hexdigest()
    if reported_hash != actual_hash:
        raise RuntimeError(f"quickfile digest drifted: reported {reported_hash}, computed {actual_hash}")
    period = Period.from_year_and_code(2026, "1T")
    provider = build_runtime_schema_provider(modelos=("115",), filing_year=2026, period=period)
    layout = provider.get_subview("115").export_layouts[0]
    parsed = parse_export_payload(layout, payload)
    if not parsed.fields:
        raise RuntimeError("production export parser returned no fields for the Modelo 115 fichero")
    return rows


@cache
def _font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    """Load the bundled, digest-pinned Cascadia Mono font."""
    if not FONT_PATH.is_file():
        raise RuntimeError(f"README renderer font is missing: {FONT_PATH}")
    font_hash = sha256(FONT_PATH.read_bytes()).hexdigest()
    if font_hash != _FONT_SHA256:
        raise RuntimeError(f"README renderer font digest drifted: {font_hash}")
    return ImageFont.truetype(str(FONT_PATH), size=size)


def _wrapped_lines(
    text: str,
    *,
    font: ImageFont.FreeTypeFont | ImageFont.ImageFont,
    width: int,
    indent: str = "",
) -> list[str]:
    """Wrap terminal text to the available pixel width."""
    probe = Image.new("RGB", (1, 1))
    draw = ImageDraw.Draw(probe)
    character_width = max(draw.textlength("M", font=font), 1)
    columns = max(int(width / character_width), 20)
    return textwrap.wrap(
        text,
        width=columns,
        subsequent_indent=indent,
        replace_whitespace=False,
        drop_whitespace=False,
        break_long_words=True,
        break_on_hyphens=False,
    ) or [""]


def _row_colour(row: str) -> str:
    """Return a semantic terminal colour without relying on colour alone."""
    if row.startswith("stage") and "\twarning\t" in row:
        return _YELLOW
    if row.startswith("stage") and "\tok" in row:
        return _GREEN
    if row == "completed\ttrue":
        return _GREEN
    return _TEXT


def _draw_frame(command: str, rows: tuple[str, ...]) -> Image.Image:
    """Draw one terminal frame for the typed command and visible output rows."""
    image = Image.new("RGB", (_WIDTH, _HEIGHT), _BACKGROUND)
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((24, 24, _WIDTH - 24, _HEIGHT - 24), radius=18, fill=_TERMINAL, outline=_BORDER, width=2)
    draw.rounded_rectangle((24, 24, _WIDTH - 24, 76), radius=18, fill="#F3EFE8", outline=_BORDER, width=2)
    draw.rectangle((24, 58, _WIDTH - 24, 76), fill="#F3EFE8")
    for x, colour in ((52, _CORAL), (78, _YELLOW), (104, _GREEN)):
        draw.ellipse((x, 42, x + 14, 56), fill=colour)

    title_font = _font(16)
    body_font = _font(18)
    draw.text((132, 39), "Cadrumo · Modelo 115", font=title_font, fill=_MUTED)

    left = 52
    top = 100
    line_height = 27
    content_width = _WIDTH - 104
    command_lines = _wrapped_lines(f"$ {command}", font=body_font, width=content_width, indent="  ")
    for line in command_lines:
        draw.text((left, top), line, font=body_font, fill=_CORAL)
        top += line_height
    if rows:
        top += 8

    for row in rows:
        visible_row = row.replace("\t", "  ")
        if row.startswith("output_path\t"):
            visible_row = visible_row.replace("\\", "/")
        for line in _wrapped_lines(visible_row, font=body_font, width=content_width, indent="  "):
            draw.text((left, top), line, font=body_font, fill=_row_colour(row))
            top += line_height
    return image


def _render(rows: tuple[str, ...]) -> None:
    """Animate the command and captured output into one optimized GIF."""
    frames: list[Image.Image] = []
    durations: list[int] = []

    frames.append(_draw_frame("", ()))
    durations.append(500)
    for end in range(3, len(DISPLAY_COMMAND) + 3, 3):
        frames.append(_draw_frame(DISPLAY_COMMAND[:end], ()))
        durations.append(55)
    durations[-1] = 450
    for count in range(1, len(rows) + 1):
        frames.append(_draw_frame(DISPLAY_COMMAND, rows[:count]))
        durations.append(170)
    durations[-1] = 2600

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    palette_frames = [frame.convert("P", palette=Image.Palette.ADAPTIVE, colors=128) for frame in frames]
    palette_frames[0].save(
        OUTPUT_PATH,
        save_all=True,
        append_images=palette_frames[1:],
        duration=durations,
        loop=0,
        optimize=True,
        disposal=2,
    )


def main() -> None:
    """Prepare synthetic data, capture the real CLI output, and render the GIF."""
    prepare_demo()
    rows = _run_quickfile()
    _render(rows)
    print(f"rendered {OUTPUT_PATH.relative_to(REPO_ROOT)} ({OUTPUT_PATH.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
