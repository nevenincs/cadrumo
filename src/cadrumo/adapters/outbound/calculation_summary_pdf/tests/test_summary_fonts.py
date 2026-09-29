"""The shipped summary faces embed with glyph widths that agree with their programs.

Archival validators require the widths a PDF font dictionary declares to match
the advance widths inside the embedded font program. The page writer computes
both from the source face, and it computes them inconsistently for a face whose
horizontal metrics use the compact form and whose em is not 1000 units: glyphs
past the last full metric record get a width already scaled to 1000 units
written back as a font-unit advance. So every shipped face is measured the way a
validator measures it -- render text in it, then compare each declared width with
the embedded subset's own advance -- and a fixture face built to have exactly the
defective shape proves the measurement catches it.

The TrueType parsing here is the minimum a width comparison needs, and it lives
in the test because nothing in the product reads font tables.
"""

from __future__ import annotations

import io
import struct
from pathlib import Path

import pikepdf
import pytest
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas

from .....application.modelo.calculation_summary_presentation import build_calculation_summary_presentation
from .....core.external_constants import OutputLanguage
from .....core.resources.bundled_data import bundled_path
from ..summary_fonts import FONT_DIRECTORY, SUMMARY_FONT_FILES, SummaryFace
from .summary_report_support import synthetic_report

pytestmark = [pytest.mark.unit, pytest.mark.hex_outbound_adapter]

_WIDTH_TOLERANCE = 1.0
_COMPACT_FULL_RECORDS = 4
_FIXTURE_NAME = "CompactMetricsFixture"


def _tables(font: bytes) -> dict[bytes, bytes]:
    count = struct.unpack(">H", font[4:6])[0]
    tables: dict[bytes, bytes] = {}
    for index in range(count):
        tag, _checksum, offset, length = struct.unpack(">4sIII", font[12 + 16 * index : 28 + 16 * index])
        tables[tag] = font[offset : offset + length]
    return tables


def _advances(font: bytes) -> tuple[int, list[int]]:
    """Return the face's units per em and every glyph's advance width in font units."""
    tables = _tables(font)
    units_per_em = struct.unpack(">H", tables[b"head"][18:20])[0]
    full_records = struct.unpack(">H", tables[b"hhea"][34:36])[0]
    glyphs = struct.unpack(">H", tables[b"maxp"][4:6])[0]
    metrics = tables[b"hmtx"]
    advances = [struct.unpack(">H", metrics[4 * index : 4 * index + 2])[0] for index in range(full_records)]
    return units_per_em, advances + [advances[-1]] * (glyphs - full_records)


def _code_to_glyph(font: bytes) -> dict[int, int]:
    """Read a subset's single-byte character map (formats 0 and 6, which subsets use)."""
    cmap = _tables(font)[b"cmap"]
    subtables = struct.unpack(">H", cmap[2:4])[0]
    for index in range(subtables):
        offset = struct.unpack(">I", cmap[8 + 8 * index : 12 + 8 * index])[0]
        form = struct.unpack(">H", cmap[offset : offset + 2])[0]
        if form == 0:
            return {code: cmap[offset + 6 + code] for code in range(256)}
        if form == 6:
            first, count = struct.unpack(">HH", cmap[offset + 6 : offset + 10])
            return {
                first + index: struct.unpack(">H", cmap[offset + 10 + 2 * index : offset + 12 + 2 * index])[0]
                for index in range(count)
            }
    raise AssertionError("the embedded subset carries no single-byte character map")


def width_defects(payload: bytes) -> list[tuple[str, int, float, float]]:
    """Return every declared width that disagrees with the embedded program's advance."""
    defects: list[tuple[str, int, float, float]] = []
    with pikepdf.open(io.BytesIO(payload)) as pdf:
        for page in pdf.pages:
            fonts = page.obj.Resources.get("/Font", pikepdf.Dictionary())
            for _name, font in fonts.items():
                # The page writer's own default face is a standard font it never
                # embeds; only embedded programs have widths to disagree with.
                if "/FontDescriptor" not in font:
                    continue
                program = font.FontDescriptor.FontFile2.read_bytes()
                units_per_em, advances = _advances(program)
                glyph_for = _code_to_glyph(program)
                first = int(font.FirstChar)
                for offset, declared in enumerate(font.Widths):
                    code = first + offset
                    embedded = advances[glyph_for.get(code, 0)] * 1000 / units_per_em
                    if abs(float(declared) - embedded) > _WIDTH_TOLERANCE:
                        defects.append((str(font.BaseFont), code, float(declared), embedded))
    return defects


def _sample_text() -> str:
    """Every character a summary sets in any language, plus the figure and hex alphabets."""
    characters: set[str] = set("0123456789abcdef.,-+·:/()%—… ")
    for language in OutputLanguage:
        presentation = build_calculation_summary_presentation(
            synthetic_report(language),
            csv_sha256="0" * 64,
            signing_key_fingerprint="f" * 64,
            brand="CADRUMO",
        )
        characters.update(presentation.model_dump_json())
    return "".join(sorted(character for character in characters if character.isprintable()))


def _render_in(face_name: str, font_path: Path) -> bytes:
    if face_name not in pdfmetrics.getRegisteredFontNames():
        pdfmetrics.registerFont(TTFont(face_name, str(font_path)))
    buffer = io.BytesIO()
    page = canvas.Canvas(buffer, invariant=1, pageCompression=0)
    text = _sample_text()
    for line_start in range(0, len(text), 60):
        page.setFont(face_name, 9)
        page.drawString(20, 800 - line_start // 60 * 12, text[line_start : line_start + 60])
    page.showPage()
    page.save()
    return buffer.getvalue()


def _compact_metrics_fixture(font: bytes, *, postscript_name: str) -> bytes:
    """Rewrite ``font`` into the shape the page writer mis-subsets.

    Keeps only the first few full horizontal-metric records, leaving every later
    glyph to inherit the last advance, and doubles the units per em so a scaled
    width and a font-unit advance can no longer coincide. The face is renamed,
    in place and at the same length, because the page writer shares one face per
    PostScript name across a process: a fixture keeping the shipped name would be
    measured as the shipped face.
    """
    tables = _tables(font)
    renamed = (_FIXTURE_NAME * 4)[: len(postscript_name)]
    tables[b"name"] = (
        tables[b"name"]
        .replace(postscript_name.encode("ascii"), renamed.encode("ascii"))
        .replace(postscript_name.encode("utf-16-be"), renamed.encode("utf-16-be"))
    )
    hhea = bytearray(tables[b"hhea"])
    head = bytearray(tables[b"head"])
    full_records = struct.unpack(">H", hhea[34:36])[0]
    glyphs = struct.unpack(">H", tables[b"maxp"][4:6])[0]
    metrics = tables[b"hmtx"]
    pairs = [struct.unpack(">Hh", metrics[4 * index : 4 * index + 4]) for index in range(full_records)]
    bearings = [pair[1] for pair in pairs] + [
        struct.unpack(">h", metrics[4 * full_records + 2 * index : 4 * full_records + 2 * index + 2])[0]
        for index in range(glyphs - full_records)
    ]
    kept = _COMPACT_FULL_RECORDS
    tables[b"hmtx"] = b"".join(struct.pack(">Hh", pairs[index][0], bearings[index]) for index in range(kept)) + (
        b"".join(struct.pack(">h", bearing) for bearing in bearings[kept:])
    )
    struct.pack_into(">H", hhea, 34, kept)
    struct.pack_into(">H", head, 18, struct.unpack(">H", head[18:20])[0] * 2)
    tables[b"hhea"] = bytes(hhea)
    tables[b"head"] = bytes(head)
    tags = sorted(tables)
    directory = b""
    body = b""
    first_offset = 12 + 16 * len(tags)
    for tag in tags:
        table = tables[tag]
        padded = table + b"\0" * (-len(table) % 4)
        checksum = sum(struct.unpack(f">{len(padded) // 4}I", padded)) & 0xFFFFFFFF
        directory += struct.pack(">4sIII", tag, checksum, first_offset + len(body), len(table))
        body += padded
    return font[:12] + directory + body


@pytest.mark.parametrize("face", tuple(SummaryFace))
def test_every_shipped_face_embeds_widths_that_match_its_program(face: SummaryFace) -> None:
    """A validator comparing declared and embedded widths finds nothing to refuse."""
    font_path = bundled_path(*FONT_DIRECTORY, SUMMARY_FONT_FILES[face])
    payload = _render_in(f"WidthGate-{face}", font_path)

    assert width_defects(payload) == []


def test_the_width_gate_refuses_a_compact_metrics_face(tmp_path: Path) -> None:
    """Detector teeth: a face in the mis-subset shape is caught by the same measurement."""
    filename = SUMMARY_FONT_FILES[next(iter(SUMMARY_FONT_FILES))]
    shipped = bundled_path(*FONT_DIRECTORY, filename).read_bytes()
    fixture = tmp_path / "compact-metrics.ttf"
    fixture.write_bytes(_compact_metrics_fixture(shipped, postscript_name=filename.removesuffix(".ttf")))

    defects = width_defects(_render_in("WidthGate-compact-metrics-fixture", fixture))

    assert defects, "a compact-metrics face with a non-1000 em must produce inconsistent widths"


def test_every_shipped_family_carries_its_licence_text() -> None:
    """Each face ships beside the SIL OFL text of its family."""
    for filename in SUMMARY_FONT_FILES.values():
        family = filename.split("-", 1)[0]
        licence = bundled_path(*FONT_DIRECTORY, f"{family}-OFL.txt").read_text(encoding="utf-8")
        assert "SIL Open Font License" in licence
        assert family.replace("Grotesk", " Grotesk").replace("Mono", " Mono") in licence
