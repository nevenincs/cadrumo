"""Unit tests for the verification registry boundary."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from ...adapters.inbound.declaracion import (
    DeclaracionFiling,
    ExtractionStatus,
    ExtractionWarning,
    TemplateRevision,
)
from ...adapters.inbound.pdf._shared import ExtractedCasilla
from . import (
    VerificationError,
    VerificationStatus,
    VerificationVerdict,
    verify_declaracion,
)

pytestmark = [pytest.mark.unit, pytest.mark.domain_application]


def _build_filing(
    *,
    values: tuple[tuple[str, Decimal], ...],
    warnings: tuple[ExtractionWarning, ...] = (),
    modelo: str = "130",
    period: str = "2025Q1",
    ejercicio: str = "2025",
) -> DeclaracionFiling:
    """Assemble a synthetic
    :class:`aeat.adapters.inbound.declaracion.DeclaracionFiling`.
    """
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


def test_verify_declaracion_uses_modelo_130_registry_snapshot() -> None:
    filing = _build_filing(
        values=(
            ("01", Decimal("10000")),
            ("02", Decimal("4000")),
            ("03", Decimal("6000.00")),
            ("04", Decimal("1200.00")),
            ("05", Decimal("250")),
            ("06", Decimal("100")),
            ("07", Decimal("850.00")),
            ("08", Decimal("2000")),
            ("09", Decimal("40.00")),
            ("10", Decimal("10")),
            ("11", Decimal("30.00")),
            ("12", Decimal("880.00")),
            ("13", Decimal("0")),
            ("14", Decimal("880.00")),
            ("15", Decimal("0")),
            ("16", Decimal("0")),
            ("17", Decimal("880.00")),
            ("18", Decimal("0")),
            ("19", Decimal("880.00")),
        )
    )

    verdict = verify_declaracion(filing)

    assert verdict.registry_snapshot_id == "registry:130:2019-y-siguientes"
    assert verdict.status is VerificationStatus.VERIFIED
    assert verdict.coverage == 1.0
    assert verdict.discrepancies == ()


def test_verify_declaracion_classifies_registry_divergence() -> None:
    filing = _build_filing(
        values=(
            ("01", Decimal("10000")),
            ("02", Decimal("4000")),
            ("19", Decimal("999.00")),
        )
    )

    verdict = verify_declaracion(filing)

    assert verdict.status is VerificationStatus.NEEDS_REVIEW
    assert verdict.discrepancies[0].casilla_id == "19"


def test_verify_declaracion_fails_without_registry_snapshot() -> None:
    filing = _build_filing(values=(("01", Decimal("0")),), modelo="303")

    with pytest.raises(VerificationError, match="not present in the calculation registry"):
        verify_declaracion(filing)


class TestVerdictJsonRoundTrip:
    """JSON serialisation invariants for
    :class:`aeat.application.verification.VerificationVerdict`.
    """

    def test_verdict_is_json_serialisable(self) -> None:
        """Verify a verdict survives ``model_dump_json`` round-trip."""
        verdict = VerificationVerdict(
            modelo="130",
            period="2025Q1",
            registry_snapshot_id="registry:130:2019-y-siguientes",
            status=VerificationStatus.VERIFIED,
            discrepancies=(),
            coverage=1.0,
            narrative={
                "es": "Verificacion completada contra el registro.",
                "en": "Verification completed against the registry.",
            },
            verified_at=datetime(2026, 5, 3, tzinfo=UTC),
        )
        serialised = verdict.model_dump_json()
        reloaded = VerificationVerdict.model_validate_json(serialised)
        assert reloaded == verdict
