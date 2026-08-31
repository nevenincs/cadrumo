"""Synthetic justificante PDF generator for the #44 parser test suite.

This script produces deterministic synthetic *justificantes de presentacion*
for Modelo 130, Modelo 303, Modelo 100, and Modelo 840 under
``src/cadrumo/tests/fixtures/justificantes/``. The PDFs are hand-modelled on the public
AEAT receipt layout (header, modelo/periodo/ejercicio block, NIF, CSV, URL,
totals) but every identifier is fictitious â€” the fixtures contain no real
taxpayer data.

The M840 fixture reproduces the Apartado II label layout from the AEAT-published
printed form at:
  src/cadrumo/_data/corpus/aeat_official/forms/modelo_840/files/
    01-840-modelo-declaracion-iae-alta-variacion-baja-pdf.pdf
pdfplumber extracts the label lines as "14Ejercicio: <value>" and
"15Declaracion de: <value>" â€” the fixture uses the same casilla-number-prefixed
format so the named_label parser can locate and extract the values.

The PDFs are **committed** to the repo. This script exists as a reference so
they can be regenerated deterministically; it is not executed by the test
suite. Run manually with ``uv run python src/cadrumo/tests/fixtures/justificantes/_generate.py``.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas

from ....core.external_constants import UTF_8_ENCODING, load_external_constants
from ..provenance import FIXTURE_PROVENANCE_SYNTHETIC

SYNTHETIC_SANITIZER_VERSION = "0.1.0-synthetic"
"""Sidecar ``sanitizer_version`` for a generator-produced specimen.

Deliberately distinct from the production ``SANITIZER_VERSION``: that one
stamps a REAL AEAT document put through the redaction pipeline, while this
one stamps a specimen the generator authored outright, which was never
sanitised because it never carried taxpayer data. A reader comparing the two
values is asking which of those two histories a fixture has, so collapsing
them would erase the distinction the provenance gate exists to check.

Named here rather than inlined at the write site so both halves of that pair
have a declared home and can be cross-referenced.
"""


@dataclass(frozen=True)
class _Fixture:
    filename: str
    modelo: str
    ejercicio: str
    periodo: str
    tax_id: str
    full_name: str
    csv: str
    presented_at: str
    presentation_id: str
    total_ingresar: str | None
    total_devolver: str | None


_FIXTURES: tuple[_Fixture, ...] = (
    _Fixture(
        filename="modelo_130_2026Q1.pdf",
        modelo="130",
        ejercicio="2026",
        periodo="1T",
        tax_id="00000000T",
        full_name="DEMO AUTONOMO UNO",
        csv="ABCD1234EFGH5678",
        presented_at="2026-04-10 11:23:45",
        presentation_id="13020260410ABCD1234EFGH5678",
        total_ingresar="1234.56",
        total_devolver=None,
    ),
    _Fixture(
        filename="modelo_303_2026Q1.pdf",
        modelo="303",
        ejercicio="2026",
        periodo="1T",
        tax_id="00000000T",
        full_name="DEMO AUTONOMO UNO",
        csv="ZZZZ9999YYYY8888",
        presented_at="2026-04-11 09:05:00",
        presentation_id="30320260411ZZZZ9999YYYY8888",
        total_ingresar=None,
        total_devolver="450.00",
    ),
    _Fixture(
        filename="modelo_100_2025A.pdf",
        modelo="100",
        ejercicio="2025",
        periodo="0A",
        tax_id="00000000T",
        full_name="DEMO AUTONOMO UNO",
        csv="MNOP4321QRST8765",
        presented_at="2026-06-20 17:45:12",
        presentation_id="10020260620MNOP4321QRST8765",
        total_ingresar="780.40",
        total_devolver=None,
    ),
)

_AEAT_CONSTANTS = load_external_constants().aeat

_SEDE_ORIGIN = _AEAT_CONSTANTS.domains.sede

_VERIFY_URL = f"{_SEDE_ORIGIN}{_AEAT_CONSTANTS.help_pages.csv_verification}"


def _draw(c: canvas.Canvas, fixture: _Fixture) -> None:
    """Render a single synthetic justificante page onto ``c``."""
    _, height = A4
    y = height - 25 * mm
    c.setFont("Helvetica-Bold", 14)
    c.drawString(20 * mm, y, "AGENCIA TRIBUTARIA")
    y -= 8 * mm
    c.setFont("Helvetica-Bold", 12)
    c.drawString(20 * mm, y, "Justificante de presentacion")
    y -= 12 * mm
    c.setFont("Helvetica", 10)
    c.drawString(20 * mm, y, f"Modelo: {fixture.modelo}")
    y -= 6 * mm
    c.drawString(20 * mm, y, f"Ejercicio: {fixture.ejercicio}")
    y -= 6 * mm
    c.drawString(20 * mm, y, f"Periodo: {fixture.periodo}")
    y -= 10 * mm
    c.drawString(20 * mm, y, f"NIF: {fixture.tax_id}")
    y -= 6 * mm
    c.drawString(20 * mm, y, f"Apellidos y nombre o razon social: {fixture.full_name}")
    y -= 10 * mm
    c.drawString(20 * mm, y, f"Numero de justificante: {fixture.presentation_id}")
    y -= 6 * mm
    c.drawString(20 * mm, y, f"Fecha y hora de presentacion: {fixture.presented_at}")
    y -= 6 * mm
    c.drawString(20 * mm, y, "Fecha de alta de la actividad: 01-01-1900")
    y -= 10 * mm
    c.drawString(20 * mm, y, f"Codigo Seguro de Verificacion: {fixture.csv}")
    y -= 10 * mm
    if fixture.total_ingresar is not None:
        c.drawString(20 * mm, y, f"Total a ingresar: {fixture.total_ingresar} euros")
        y -= 6 * mm
    if fixture.total_devolver is not None:
        c.drawString(20 * mm, y, f"Total a devolver: {fixture.total_devolver} euros")
        y -= 6 * mm
    y -= 8 * mm
    c.drawString(20 * mm, y, "Puede verificar la autenticidad de este documento en:")
    y -= 6 * mm
    c.drawString(20 * mm, y, _VERIFY_URL)


def _write_sidecar(
    pdf_path: Path,
    modelo: str,
    ejercicio: str,
    tax_id: str,
    *,
    role: str = "formula_verification",
) -> None:
    """Write a sanitiser-manifest sidecar JSON for a synthetic fixture PDF.

    The sidecar format mirrors the real sanitiser manifest consumed by
    ``test_corpus_sidecar_roundtrip.py``'s ``_load_ground_truth``.  The
    ``replacements_applied`` list must contain a ``SANITIZED{modelo}{ejercicio}``
    token so the roundtrip test can derive the expected CSV ground truth.

    ``role`` and ``provenance`` are ORTHOGONAL axes, per the accepted
    verification-fixture-roles decision: provenance records where the bytes came
    from, role records what the specimen is kept for. Everything this generator
    writes is ``synthetic_generated``, but a synthetic specimen authored to
    reproduce a real form's printed layout is a ``parser_anchor`` and not a
    ``formula_verification`` one -- its amounts are probes, and a reader that
    took them for internally-consistent figures would be reading them for more
    than they are worth. The default is the common case; a layout replacement
    passes ``role="parser_anchor"`` explicitly.

    The pdf_path must already exist (written by the caller before calling this).
    """
    pdf_bytes = pdf_path.read_bytes()
    pdf_sha256 = hashlib.sha256(pdf_bytes).hexdigest()
    sidecar_data = {
        # Fixture-provenance declaration consumed by the verification-source
        # gate: this writer only ever emits synthetic, generator-produced
        # specimens, whose PDFs carry SYNTHETIC_FIXTURE_PRODUCER as /Producer.
        "provenance": FIXTURE_PROVENANCE_SYNTHETIC,
        "role": role,
        "source_sha256": pdf_sha256,
        "output_sha256": pdf_sha256,
        "source_size_bytes": len(pdf_bytes),
        "output_size_bytes": len(pdf_bytes),
        "sanitizer_version": SYNTHETIC_SANITIZER_VERSION,
        "determinism_flags": {
            "deterministic_id": True,
            "static_id": False,
            "object_stream_mode": "preserve",
            "linearize": False,
            "recompress_flate": False,
            "compress_streams": True,
        },
        "replacements_applied": [
            {
                "surface": "content_stream",
                "surface_index": [0, 0],
                "real_sha256": "0" * 64,
                "synthetic": "01-01-1900",
                "encoding": "literal",
            },
            {
                "surface": "content_stream",
                "surface_index": [0, 1],
                "real_sha256": "0" * 64,
                "synthetic": f"SANITIZED{modelo}{ejercicio}",
                "encoding": "literal",
            },
            {
                "surface": "content_stream",
                "surface_index": [0, 2],
                "real_sha256": "0" * 64,
                "synthetic": tax_id,
                "encoding": "literal",
            },
        ],
        "surfaces_scrubbed": [],
        "warnings": [],
    }
    sidecar_path = pdf_path.with_suffix(".json")
    sidecar_path.write_text(json.dumps(sidecar_data, indent=2), encoding=UTF_8_ENCODING, newline="\n")
    print(f"wrote sidecar {sidecar_path}")
