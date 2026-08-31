"""Unit tests for :mod:`cadrumo.adapters.inbound.pdf.extracted_casilla`.

Exercises the strict + frozen invariants of :class:`ExtractedCasilla`
(value-type tolerance, frozen attributes, source-page bounds,
extraction-confidence range, bounding-box shape, JSON round-trip) and
the :class:`PdfModeloImportError` root's inheritance chain.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from pydantic import ValidationError

from .....core.casilla_id import CasillaId, validated_casilla_id
from .....core.errors.hierarchy import CadrumoError
from .. import ExtractedCasilla, PdfModeloImportError

pytestmark = [pytest.mark.unit, pytest.mark.hex_inbound_adapter]

_PrintedValue = Decimal | int | str | bool | date | None
_DEFAULT_CASILLA: CasillaId = validated_casilla_id("01", surface="_DEFAULT_CASILLA")
_OTHER_CASILLA: CasillaId = validated_casilla_id("02", surface="_OTHER_CASILLA")


class TestExtractedCasillaShape:
    """Strict + frozen invariants of :class:`ExtractedCasilla`."""

    def _build(
        self,
        *,
        casilla_id: CasillaId = _DEFAULT_CASILLA,
        printed_value: _PrintedValue = Decimal("1234.56"),
        source_page: int = 1,
        source_bbox: tuple[float, float, float, float] | None = None,
        extraction_confidence: float = 1.0,
    ) -> ExtractedCasilla:
        """Build a populated :class:`ExtractedCasilla` for assertion targets."""
        return ExtractedCasilla(
            casilla_id=casilla_id,
            printed_value=printed_value,
            source_page=source_page,
            source_bbox=source_bbox,
            extraction_confidence=extraction_confidence,
        )

    def test_builds_with_decimal_value(self) -> None:
        record = self._build()
        assert record.casilla_id == _DEFAULT_CASILLA
        assert record.printed_value == Decimal("1234.56")
        assert record.extraction_confidence == 1.0

    def test_accepts_every_documented_value_type(self) -> None:
        for value in (Decimal("0"), 42, "SII", True, date(2025, 1, 1), None):
            record = self._build(printed_value=value)
            assert record.printed_value == value

    def test_is_frozen(self) -> None:
        record = self._build()
        with pytest.raises(ValidationError, match=r"frozen|Instance is frozen"):
            record.casilla_id = _OTHER_CASILLA

    def test_extra_fields_rejected(self) -> None:
        with pytest.raises(ValidationError, match=r"Extra inputs are not permitted"):
            ExtractedCasilla.model_validate(
                {
                    "casilla_id": _DEFAULT_CASILLA,
                    "printed_value": Decimal("1.00"),
                    "source_page": 1,
                    "extraction_confidence": 1.0,
                    "surprise": "not allowed",
                },
            )

    def test_source_page_must_be_positive(self) -> None:
        with pytest.raises(ValidationError, match=r"source_page|greater than"):
            self._build(source_page=0)

    def test_extraction_confidence_bounded(self) -> None:
        with pytest.raises(ValidationError, match=r"extraction_confidence|greater than|less than"):
            self._build(extraction_confidence=-0.1)
        with pytest.raises(ValidationError, match=r"extraction_confidence|greater than|less than"):
            self._build(extraction_confidence=1.1)

    def test_bbox_accepts_four_floats(self) -> None:
        record = self._build(source_bbox=(10.0, 20.0, 30.0, 40.0))
        assert record.source_bbox == (10.0, 20.0, 30.0, 40.0)

    def test_bbox_rejects_wrong_shape(self) -> None:
        with pytest.raises(ValidationError, match=r"source_bbox|Tuple should have"):
            ExtractedCasilla.model_validate(
                {
                    "casilla_id": _DEFAULT_CASILLA,
                    "printed_value": Decimal("0"),
                    "source_page": 1,
                    "source_bbox": (10.0, 20.0, 30.0),
                    "extraction_confidence": 1.0,
                },
            )

    def test_json_roundtrip(self) -> None:
        record = self._build(source_bbox=(1.0, 2.0, 3.0, 4.0))
        dumped = record.model_dump_json()
        reloaded = ExtractedCasilla.model_validate_json(dumped)
        assert reloaded == record


class TestPdfModeloImportError:
    """The shared error root inherits from :class:`CadrumoError`."""

    def test_is_cadrumo_error(self) -> None:
        assert issubclass(PdfModeloImportError, CadrumoError)

    def test_can_be_caught_as_cadrumo_error(self) -> None:
        with pytest.raises(CadrumoError, match=r"test"):
            raise PdfModeloImportError("test")

    def test_can_be_caught_as_pdf_filing_import_error(self) -> None:
        with pytest.raises(PdfModeloImportError, match=r"test"):
            raise PdfModeloImportError("test")
