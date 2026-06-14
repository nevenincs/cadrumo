"""Unit tests for the verification registry boundary."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from ....adapters.inbound.declaracion import (
    DeclaracionObservation,
    ExtractionWarning,
    TemplateRevision,
)
from ....adapters.inbound.pdf._shared import ExtractedCasilla
from ....core import Period
from ....core.errors import render_error_json, render_error_text
from .. import (
    VerificationError,
    VerificationStatus,
    VerificationVerdict,
    verify_declaracion,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def _build_filing(
    *,
    values: tuple[tuple[str, Decimal], ...],
    warnings: tuple[ExtractionWarning, ...] = (),
    modelo: str = "130",
    period: str = "1T",
    ejercicio: str = "2025",
) -> DeclaracionObservation:
    """Build a parsed declaration boundary object for verification."""
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
    return DeclaracionObservation(
        modelo=modelo,
        period=Period.from_year_and_code(int(ejercicio), period),
        ejercicio=ejercicio,
        tax_id="00000000T",
        template_revision=TemplateRevision(
            modelo=modelo,
            año=int(ejercicio),
            revision=f"{ejercicio}.01",
        ),
        values=extracted,
        warnings=warnings,
        source_pdf_path=Path(f"modelo-{modelo}-declaracion.pdf"),
        source_pdf_sha256="0" * 64,
        parsed_at=datetime.now(tz=UTC),
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
        ),
    )

    verdict = verify_declaracion(
        filing,
        binding_values={
            "irpf.previous_year_economic_activity_net_income": Decimal("13000"),
            "modelo-130-actividad-economica-ingresos-taxable-base-cumulative": Decimal("0"),
            "modelo-130-actividad-economica-rendimiento-neto-cumulative": Decimal("0"),
            "modelo-130-resultados-negativos-anteriores": Decimal("0"),
            "modelo-130-pagos-fraccionados-anteriores": Decimal("250"),
        },
    )

    assert verdict.registry_snapshot_id == "registry:130:2019-y-siguientes"
    assert verdict.verification_expectation_ids == ("modelo-130-calculation-verification",)
    assert verdict.status is VerificationStatus.VERIFIED
    assert verdict.coverage == 1.0
    assert verdict.discrepancies == ()


def test_verify_declaracion_classifies_registry_divergence() -> None:
    filing = _build_filing(
        values=(
            ("01", Decimal("10000")),
            ("02", Decimal("4000")),
            ("19", Decimal("999.00")),
        ),
    )

    verdict = verify_declaracion(
        filing,
        binding_values={
            "irpf.previous_year_economic_activity_net_income": Decimal("13000"),
            "modelo-130-actividad-economica-ingresos-taxable-base-cumulative": Decimal("0"),
            "modelo-130-actividad-economica-rendimiento-neto-cumulative": Decimal("0"),
            "modelo-130-resultados-negativos-anteriores": Decimal("0"),
        },
    )

    assert verdict.status is VerificationStatus.NEEDS_REVIEW
    assert verdict.discrepancies[0].casilla_id == "19"


def test_verify_declaracion_uses_modelo_115_registry_snapshot() -> None:
    filing = _build_filing(
        modelo="115",
        period="1T",
        ejercicio="2026",
        values=(
            ("01", Decimal("1")),
            ("02", Decimal("1250.50")),
            ("03", Decimal("237.60")),
            ("04", Decimal("10.00")),
            ("05", Decimal("227.60")),
        ),
    )

    verdict = verify_declaracion(filing)

    assert verdict.registry_snapshot_id == "registry:115:2019-y-siguientes"
    assert verdict.verification_expectation_ids == ("modelo-115-calculation-verification",)
    assert verdict.status is VerificationStatus.VERIFIED
    assert verdict.coverage == 1.0
    assert verdict.discrepancies == ()


def test_verify_declaracion_uses_modelo_123_current_registry_snapshot() -> None:
    filing = _build_filing(
        modelo="123",
        period="1T",
        ejercicio="2026",
        values=(
            ("01", Decimal("2")),
            ("02", Decimal("3")),
            ("03", Decimal("5")),
            ("04", Decimal("1000.25")),
            ("05", Decimal("200.75")),
            ("06", Decimal("1201.00")),
            ("07", Decimal("190.05")),
            ("08", Decimal("38.14")),
            ("09", Decimal("228.19")),
            ("10", Decimal("0")),
            ("11", Decimal("7.50")),
            ("12", Decimal("235.69")),
            ("13", Decimal("12.25")),
            ("14", Decimal("223.44")),
        ),
    )

    verdict = verify_declaracion(filing)

    assert verdict.registry_snapshot_id == "registry:123:2024-y-siguientes"
    assert verdict.verification_expectation_ids == ("modelo-123-calculation-verification",)
    assert verdict.status is VerificationStatus.VERIFIED
    assert verdict.coverage == 1.0
    assert verdict.discrepancies == ()


def test_verify_declaracion_uses_modelo_123_historical_registry_snapshot() -> None:
    filing = _build_filing(
        modelo="123",
        period="1T",
        ejercicio="2023",
        values=(
            ("01-legacy", Decimal("2")),
            ("02-legacy", Decimal("1000.25")),
            ("03-legacy", Decimal("190.05")),
            ("04-legacy", Decimal("0")),
            ("05-legacy", Decimal("7.50")),
            ("06-legacy", Decimal("197.55")),
            ("07-legacy", Decimal("12.25")),
            ("08-legacy", Decimal("185.30")),
        ),
    )

    verdict = verify_declaracion(filing)

    assert verdict.registry_snapshot_id == "registry:123:2019-2023"
    assert verdict.verification_expectation_ids == ("modelo-123-2019-calculation-verification",)
    assert verdict.status is VerificationStatus.VERIFIED
    assert verdict.coverage == 1.0
    assert verdict.discrepancies == ()


def test_verify_declaracion_fails_without_registry_snapshot() -> None:
    filing = _build_filing(values=(("01", Decimal("0")),), modelo="999")

    with pytest.raises(VerificationError) as raised:
        verify_declaracion(filing)

    error = raised.value
    assert error.translated_message == "application.verification.errors.registry_snapshot_invalid"
    assert error.context == {
        "modelo": "999",
        "period": "2025 1T",
        "ejercicio": "2025",
        "error_type": "RegistrySnapshotError",
    }


def test_verify_declaracion_reports_missing_registry_bindings_as_locale_error() -> None:
    filing = _build_filing(
        values=(
            ("01", Decimal("10000")),
            ("02", Decimal("4000")),
            ("19", Decimal("880.00")),
        ),
    )

    with pytest.raises(VerificationError) as raised:
        verify_declaracion(filing)

    error = raised.value
    assert error.translated_message == "application.verification.errors.missing_binding_values"
    assert error.context == {
        "bindings": (
            "irpf.previous_year_economic_activity_net_income",
            "modelo-130-actividad-economica-ingresos-taxable-base-cumulative",
            "modelo-130-actividad-economica-rendimiento-neto-cumulative",
        ),
        "count": 3,
        "modelo": "130",
        "period": "2025 1T",
    }
    rendered_text = render_error_text(error)
    rendered_json = json.loads(render_error_json(error))
    assert "<Period>" not in rendered_text
    assert "period: 2025 1T" in rendered_text
    assert rendered_json["error"]["context"]["period"] == "2025 1T"


def test_verify_declaracion_reports_period_year_mismatch_as_verification_error() -> None:
    filing = _build_filing(values=(("01", Decimal("0")),)).model_copy(
        update={"period": Period.from_year_and_code(2024, "1T")}
    )

    with pytest.raises(VerificationError) as raised:
        verify_declaracion(filing)

    error = raised.value
    assert error.translated_message == "application.verification.errors.period_mapping_failed"
    assert error.context == {"period": "2024 1T", "ejercicio": "2025"}


class TestVerdictJsonRoundTrip:
    """JSON serialisation invariants for
    :class:`aeat.application.verification.VerificationVerdict`.
    """

    def test_verdict_is_json_serialisable(self) -> None:
        """Verify a verdict survives ``model_dump_json`` round-trip.

        The ``period`` field serialises as ``{"filing_year": 2025, "code": "1T"}``
        (the canonical :class:`~aeat.core.Period` JSON shape) and is
        reconstituted to the same :class:`~aeat.core.Period` on reload.
        """
        verdict = VerificationVerdict(
            modelo="130",
            period=Period.from_year_and_code(2025, "1T"),
            registry_snapshot_id="registry:130:2019-y-siguientes",
            verification_expectation_ids=("modelo-130-calculation-verification",),
            status=VerificationStatus.VERIFIED,
            discrepancies=(),
            coverage=1.0,
            narrative="verification.test_verify.narrative_258092",
            verified_at=datetime(2026, 5, 3, tzinfo=UTC),
        )
        serialised = verdict.model_dump_json()
        reloaded = VerificationVerdict.model_validate_json(serialised)
        assert reloaded == verdict
        assert reloaded.period == Period.from_year_and_code(2025, "1T")
