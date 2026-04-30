"""Unit tests for verify_declaracion (#305 cluster E)."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from .._pdf_import._shared import ExtractedCasilla
from ..declaracion import (
    DeclaracionFiling,
    ExtractionStatus,
    ExtractionWarning,
    TemplateRevision,
)
from ..formulas import Ruleset, get_registry
from ..models import ModeloCode
from . import (
    DiscrepancyCause,
    VerificationStatus,
    verify_declaracion,
)

pytestmark = [pytest.mark.unit, pytest.mark.domain_financial_input]


def _build_filing(
    *,
    values: tuple[tuple[str, Decimal], ...],
    warnings: tuple[ExtractionWarning, ...] = (),
    modelo: str = "130",
    period: str = "2025Q1",
    ejercicio: str = "2025",
) -> DeclaracionFiling:
    """Assemble a synthetic DeclaracionFiling with given casilla values."""
    extracted = tuple(
        ExtractedCasilla(
            casilla_id=casilla_id,
            printed_value=value,
            source_page=1,
            source_bbox=None,
            extraction_confidence=1.0,
        )
        for casilla_id, value in values
    )
    return DeclaracionFiling(
        modelo=modelo,
        period=period,
        ejercicio=ejercicio,
        tax_id="00000000T",
        template_revision=TemplateRevision(
            modelo=modelo,
            año=int(ejercicio),
            revision=f"{ejercicio}.01",
        ),
        values=extracted,
        warnings=warnings,
        source_pdf_path=Path("synthetic.pdf"),
        source_pdf_sha256="0" * 64,
        parsed_at=datetime.now(tz=UTC),
        extraction_status=ExtractionStatus.COMPLETE,
    )


def _modelo_130_2025_ruleset() -> Ruleset:
    return get_registry().resolve(
        modelo=ModeloCode.MODELO_130,
        period=_first_quarter_2025(),
    )


def _first_quarter_2025():
    from ..formulas import FiscalPeriod, Quarter

    return FiscalPeriod(year=2025, quarter=Quarter.Q1)


class TestVerifyHappyPath:
    def test_all_literals_match_derived_reports_verified(self) -> None:
        """When Kent's printed values satisfy the ruleset, status = VERIFIED."""
        # Modelo 130 ruleset for 2025Q1 computes 03 = 01 - 02, 04 = 20% of 03, 07 = max(0, 04-05-06).
        # Provide a consistent set.
        values: tuple[tuple[str, Decimal], ...] = (
            ("01", Decimal("10000.00")),
            ("02", Decimal("4000.00")),
            ("03", Decimal("6000.00")),
            ("04", Decimal("1200.00")),
            ("05", Decimal("200.00")),
            ("06", Decimal("100.00")),
            ("07", Decimal("900.00")),
        )
        filing = _build_filing(values=values)
        verdict = verify_declaracion(filing, ruleset=_modelo_130_2025_ruleset())
        assert verdict.status is VerificationStatus.VERIFIED
        assert verdict.discrepancies == ()
        assert verdict.coverage > 0


class TestVerifyDiscrepancyClassification:
    def test_correctness_divergence_needs_review(self) -> None:
        """A big delta on a ruleset casilla → CORRECTNESS_DIVERGENCE."""
        # Deliberately wrong casilla 07 — off by much more than 10 xtolerance.
        values: tuple[tuple[str, Decimal], ...] = (
            ("01", Decimal("10000.00")),
            ("02", Decimal("4000.00")),
            ("03", Decimal("6000.00")),
            ("04", Decimal("1200.00")),
            ("05", Decimal("0.00")),
            ("06", Decimal("0.00")),
            ("07", Decimal("9999.99")),  # should be 1200
        )
        filing = _build_filing(values=values)
        verdict = verify_declaracion(filing, ruleset=_modelo_130_2025_ruleset())
        assert verdict.status is VerificationStatus.NEEDS_REVIEW
        causes = {d.cause for d in verdict.discrepancies}
        assert DiscrepancyCause.CORRECTNESS_DIVERGENCE in causes

    def test_rounding_delta_classified_as_rounding(self) -> None:
        """Small delta (< 10 xtolerance) on a computed casilla → ROUNDING."""
        # Casilla 03 = 01 - 02 = 6000 exactly; introduce a 0.03 delta.
        values: tuple[tuple[str, Decimal], ...] = (
            ("01", Decimal("10000.00")),
            ("02", Decimal("4000.00")),
            ("03", Decimal("6000.03")),  # rounding-size delta
            ("04", Decimal("1200.00")),
            ("05", Decimal("0.00")),
            ("06", Decimal("0.00")),
            ("07", Decimal("1200.00")),
        )
        filing = _build_filing(values=values)
        verdict = verify_declaracion(filing, ruleset=_modelo_130_2025_ruleset())
        causes = {d.cause for d in verdict.discrepancies}
        assert DiscrepancyCause.ROUNDING in causes
        # Rounding alone is non-blocking.
        assert verdict.status in {VerificationStatus.VERIFIED, VerificationStatus.NEEDS_REVIEW}

    def test_extraction_warning_upgrades_to_unreliable(self) -> None:
        """Declaration warnings on a casilla flip its discrepancy to EXTRACTION_UNRELIABLE."""
        values: tuple[tuple[str, Decimal], ...] = (
            ("01", Decimal("10000.00")),
            ("02", Decimal("4000.00")),
            ("03", Decimal("5000.00")),  # wrong by 1000 → would be CORRECTNESS
            ("04", Decimal("1200.00")),
            ("05", Decimal("0.00")),
            ("06", Decimal("0.00")),
            ("07", Decimal("1200.00")),
        )
        warnings = (
            ExtractionWarning(
                casilla_id="03",
                code="bbox-fallback",
                message={"es": "fallback", "en": "fallback", "hu": "fallback"},
                primitive_attempted="bbox",
            ),
        )
        filing = _build_filing(values=values, warnings=warnings)
        verdict = verify_declaracion(filing, ruleset=_modelo_130_2025_ruleset())
        matching = [d for d in verdict.discrepancies if d.casilla_id == "03"]
        assert matching and matching[0].cause is DiscrepancyCause.EXTRACTION_UNRELIABLE
        assert verdict.status is VerificationStatus.NEEDS_REVIEW


class TestVerifyUnverifiable:
    def test_no_ruleset_produces_unverifiable_status(self) -> None:
        filing = _build_filing(values=(("01", Decimal("0")),))
        verdict = verify_declaracion(filing, ruleset=None)
        assert verdict.status is VerificationStatus.UNVERIFIABLE
        assert verdict.ruleset_id is None
        assert verdict.coverage == 0.0


class TestVerdictJsonRoundTrip:
    def test_verdict_is_json_serialisable(self) -> None:
        filing = _build_filing(
            values=(
                ("01", Decimal("100.00")),
                ("02", Decimal("50.00")),
                ("03", Decimal("50.00")),
                ("04", Decimal("10.00")),
                ("05", Decimal("0.00")),
                ("06", Decimal("0.00")),
                ("07", Decimal("10.00")),
            )
        )
        verdict = verify_declaracion(filing, ruleset=_modelo_130_2025_ruleset())
        serialised = verdict.model_dump_json()
        from . import VerificationVerdict

        reloaded = VerificationVerdict.model_validate_json(serialised)
        assert reloaded == verdict
