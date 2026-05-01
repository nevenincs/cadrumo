"""Round-trip tests for the Modelo 100 (IRPF annual) extractor (#239).

Parametrised over the three live AEAT-issued justificantes captured
under ``scratch/recon-corpus/``. Each case exercises the real PDF
bytes end-to-end via :func:`aeat.adapters.inbound.declaracion.parse_declaracion`, with
no synthetic regeneration — these are the canonical ground truth for
Modelo 100 layout parity.

The test set skips cleanly when the scratch captures are absent (CI
contributors without the private corpus still run green).
"""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest

from ... import parse_declaracion
from ....pdf._shared import ExtractedCasilla
from ..._schema import DeclaracionFiling, TemplateRevision

pytestmark = [
    pytest.mark.unit,
    pytest.mark.domain_inbound,
    pytest.mark.fixture_tier_l2,
]


_CORPUS_ROOT = Path(__file__).resolve().parents[7] / "scratch" / "recon-corpus" / "20260424T184450Z"


def _justificante(ejercicio: str) -> Path:
    return _CORPUS_ROOT / f"irpf-{ejercicio}" / "justificante.pdf"


def _skip_if_missing(pdf_path: Path) -> None:
    if not pdf_path.is_file():
        pytest.skip(f"Modelo 100 private capture missing: {pdf_path}")


def _values_by_id(filing: DeclaracionFiling) -> dict[str, ExtractedCasilla]:
    return {v.casilla_id: v for v in filing.values}


@pytest.mark.parametrize(
    ("ejercicio", "revision", "min_casillas"),
    [
        ("2021", "2021.legacy", 30),
        ("2022", "2022.modern", 30),
        ("2023", "2023.modern", 30),
    ],
)
def test_parses_live_irpf_justificante(
    ejercicio: str,
    revision: str,
    min_casillas: int,
) -> None:
    """Every live IRPF justificante produces a DeclaracionFiling with the expected shape.

    Each filing must resolve to Modelo 100, the correct ejercicio and
    template revision, extract the declarant NIF (casilla 01) and
    full name (casilla 02), carry at least one Decimal-typed casilla
    (rendimientos / base imponible / cuota), and present ≥ 30 unique
    casillas.
    """
    pdf_path = _justificante(ejercicio)
    _skip_if_missing(pdf_path)

    filing = parse_declaracion(pdf_path)

    assert filing.modelo == "100"
    assert filing.ejercicio == ejercicio
    assert filing.period == f"{ejercicio}A"
    assert filing.template_revision == TemplateRevision(
        modelo="100",
        año=int(ejercicio),
        revision=revision,
        detected_from="header",
    )
    assert filing.tax_id == "Y4113523X"
    assert len(filing.values) >= min_casillas

    by_id = _values_by_id(filing)

    # Identity casillas — present on every Modelo 100 filing.
    assert "01" in by_id, "casilla 01 (NIF) must be extracted"
    assert by_id["01"].printed_value == "Y4113523X"
    assert "02" in by_id, "casilla 02 (Apellidos y nombre) must be extracted"
    assert isinstance(by_id["02"].printed_value, str)
    assert "WOOTSCH" in by_id["02"].printed_value

    # At least one Decimal-typed casilla (Modelo 100 always prints a
    # base liquidable general sometida a gravamen, casilla 0505).
    decimals = [v for v in filing.values if isinstance(v.printed_value, Decimal)]
    assert len(decimals) >= 1, "at least one Decimal-valued casilla must be extracted"
    assert "0505" in by_id, "casilla 0505 (base liquidable general sometida a gravamen) missing"
    assert isinstance(by_id["0505"].printed_value, Decimal)


def test_2023_matches_known_ground_truth() -> None:
    """Cross-check a handful of 2023 casillas against the printed receipt."""
    pdf_path = _justificante("2023")
    _skip_if_missing(pdf_path)

    filing = parse_declaracion(pdf_path)
    by_id = _values_by_id(filing)

    # Base imponible / liquidable general values printed on the 2023 receipt.
    assert by_id["0435"].printed_value == Decimal("70688.81")
    assert by_id["0505"].printed_value == Decimal("70688.81")
    # Resultado de la declaración — 8.422,62 € total a ingresar.
    assert by_id["0670"].printed_value == Decimal("8422.62")
    # Header casilla 68 is the tributación-individual X marker.
    assert by_id["68"].printed_value == "X"
