"""Tests for Tier-S summary-return verification."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from ...adapters.inbound.declaracion import DeclaracionFiling, ExtractionStatus, TemplateRevision
from ...adapters.inbound.pdf import ExtractedCasilla
from ...domain.modelos.m347 import ClaveOperacion, Modelo347RecordLine
from . import VerificationStatus, verify_modelo_347_summary

pytestmark = [pytest.mark.unit, pytest.mark.domain_application]


def _record(amount: str, *, tax_id: str = "B12345678", cash: str = "0.00") -> Modelo347RecordLine:
    value = Decimal(amount)
    quarter = (value / Decimal("4")).quantize(Decimal("0.01"))
    return Modelo347RecordLine(
        declared_tax_id=tax_id,
        declared_name=f"Cliente {tax_id}",
        operation_key=ClaveOperacion.B,
        annual_operation_amount=value,
        first_quarter_amount=quarter,
        second_quarter_amount=quarter,
        third_quarter_amount=quarter,
        fourth_quarter_amount=value - (quarter * 3),
        cash_received_amount=Decimal(cash),
        cash_origin_year=2025 if Decimal(cash) > Decimal("0.00") else None,
    )


def _filing(*, summary_total: str, records: tuple[Modelo347RecordLine, ...]) -> DeclaracionFiling:
    cash_total = sum((record.cash_received_amount for record in records), Decimal("0.00"))
    cash_count = sum(1 for record in records if record.cash_received_amount > Decimal("0.00"))
    return DeclaracionFiling(
        modelo="347",
        period="2025A",
        ejercicio="2025",
        tax_id="00000000T",
        template_revision=TemplateRevision(modelo="347", año=2025, revision="2025.01"),
        values=(
            ExtractedCasilla(
                casilla_id="01",
                printed_value=Decimal(len(records)),
                source_page=1,
                extraction_confidence=1.0,
            ),
            ExtractedCasilla(
                casilla_id="02",
                printed_value=Decimal(summary_total),
                source_page=1,
                extraction_confidence=1.0,
            ),
            ExtractedCasilla(
                casilla_id="03",
                printed_value=Decimal(cash_count),
                source_page=1,
                extraction_confidence=1.0,
            ),
            ExtractedCasilla(casilla_id="04", printed_value=cash_total, source_page=1, extraction_confidence=1.0),
        ),
        modelo_347_records=records,
        source_pdf_path=Path("modelo_347_2025.pdf"),
        source_pdf_sha256="0" * 64,
        parsed_at=datetime.now(tz=UTC),
        extraction_status=ExtractionStatus.COMPLETE,
    )


def test_modelo_347_summary_verified_when_records_match_resumen() -> None:
    records = (_record("1000.00"), _record("2500.25", tax_id="B87654321", cash="6100.00"))
    verdict = verify_modelo_347_summary(_filing(summary_total="3500.25", records=records))
    assert verdict.status is VerificationStatus.VERIFIED
    assert verdict.discrepancies == ()
    assert verdict.ruleset_id is None


def test_modelo_347_summary_needs_review_when_total_differs() -> None:
    records = (_record("1000.00"), _record("2500.25", tax_id="B87654321"))
    verdict = verify_modelo_347_summary(_filing(summary_total="3500.27", records=records))
    assert verdict.status is VerificationStatus.NEEDS_REVIEW
    assert len(verdict.discrepancies) == 1
    assert verdict.discrepancies[0].casilla_id == "02"
    assert verdict.discrepancies[0].delta == Decimal("0.02")


def test_modelo_347_summary_needs_review_when_count_differs() -> None:
    records = (_record("1000.00"), _record("2500.25", tax_id="B87654321"))
    filing = _filing(summary_total="3500.25", records=records).model_copy(
        update={
            "values": (
                ExtractedCasilla(
                    casilla_id="01",
                    printed_value=Decimal("3"),
                    source_page=1,
                    extraction_confidence=1.0,
                ),
                ExtractedCasilla(
                    casilla_id="02",
                    printed_value=Decimal("3500.25"),
                    source_page=1,
                    extraction_confidence=1.0,
                ),
                ExtractedCasilla(
                    casilla_id="03",
                    printed_value=Decimal("0"),
                    source_page=1,
                    extraction_confidence=1.0,
                ),
                ExtractedCasilla(
                    casilla_id="04",
                    printed_value=Decimal("0.00"),
                    source_page=1,
                    extraction_confidence=1.0,
                ),
            )
        }
    )
    verdict = verify_modelo_347_summary(filing)
    assert verdict.status is VerificationStatus.NEEDS_REVIEW
    assert {d.casilla_id for d in verdict.discrepancies} == {"01"}


def test_modelo_347_summary_treats_omitted_zero_cash_total_as_zero() -> None:
    records = (_record("1000.00"), _record("2500.25", tax_id="B87654321"))
    filing = _filing(summary_total="3500.25", records=records).model_copy(
        update={
            "values": (
                ExtractedCasilla(
                    casilla_id="01",
                    printed_value=Decimal("2"),
                    source_page=1,
                    extraction_confidence=1.0,
                ),
                ExtractedCasilla(
                    casilla_id="02",
                    printed_value=Decimal("3500.25"),
                    source_page=1,
                    extraction_confidence=1.0,
                ),
            )
        }
    )
    verdict = verify_modelo_347_summary(filing)
    assert verdict.status is VerificationStatus.VERIFIED
    assert verdict.discrepancies == ()
