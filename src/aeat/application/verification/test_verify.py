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


def test_verify_declaracion_requires_registry_snapshot() -> None:
    filing = _build_filing(values=(("01", Decimal("0")),))
    with pytest.raises(ValueError, match="validated registry snapshot"):
        verify_declaracion(filing, ruleset=None)


class TestVerdictJsonRoundTrip:
    """JSON serialisation invariants for
    :class:`aeat.application.verification.VerificationVerdict`.
    """

    def test_verdict_is_json_serialisable(self) -> None:
        """Verify a verdict survives ``model_dump_json`` round-trip."""
        verdict = VerificationVerdict(
            modelo="130",
            period="2025Q1",
            ruleset_id=None,
            status=VerificationStatus.UNVERIFIABLE,
            discrepancies=(),
            coverage=0.0,
            narrative={
                "es": "Verificacion no disponible hasta que exista snapshot de registro.",
                "en": "Verification unavailable until a registry snapshot exists.",
            },
            verified_at=datetime(2026, 5, 3, tzinfo=UTC),
        )
        serialised = verdict.model_dump_json()
        reloaded = VerificationVerdict.model_validate_json(serialised)
        assert reloaded == verdict
