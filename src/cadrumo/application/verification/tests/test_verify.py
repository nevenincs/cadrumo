"""Unit tests for the verification registry boundary."""

from __future__ import annotations

import json
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from ....adapters.inbound.declaracion import (
    ExtractionWarning,
    InboundDeclaracionObservation,
    TemplateRevision,
)
from ....adapters.inbound.pdf import ExtractedCasilla
from ....core import CasillaId, Period, validated_casilla_id
from ....core.errors import render_error_json, render_error_text
from ....core.resources import resources
from ....domain.calculations.registry import RegistrySnapshotRef, calculate_registry_snapshot
from .. import (
    VerificationError,
    VerificationStatus,
    VerificationVerdict,
    verify_declaracion,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]
_M130_RESULTADO_CASILLA: CasillaId = validated_casilla_id("19", surface="_M130_RESULTADO_CASILLA")


def _casilla_id(value: object) -> CasillaId:
    try:
        return validated_casilla_id(value, surface="verification test casilla id")
    except ValueError as exc:
        raise AssertionError(f"verification fixture casilla key {value!r} is not a canonical casilla.id") from exc


def _build_filing(
    *,
    values: tuple[tuple[object, Decimal], ...],
    warnings: tuple[ExtractionWarning, ...] = (),
    modelo: str = "130",
    period: str = "1T",
    ejercicio: str = "2025",
    registry_revision_id: str = "2019-y-siguientes",
) -> InboundDeclaracionObservation:
    """Build a parsed declaration boundary object for verification."""
    extracted = tuple(
        ExtractedCasilla(
            casilla_id=_casilla_id(casilla_id),
            printed_value=value,
            source_page=1,
            source_bbox=None,
            extraction_confidence=1.0,
        )
        for casilla_id, value in values
    )
    return InboundDeclaracionObservation(
        modelo=modelo,
        period=Period.from_year_and_code(int(ejercicio), period),
        ejercicio=ejercicio,
        tax_id="00000000T",
        template_revision=TemplateRevision(
            modelo=modelo,
            año=int(ejercicio),
            revision=f"{ejercicio}.01",
        ),
        registry_snapshot_ref=RegistrySnapshotRef(
            modelo=modelo,
            revision_id=registry_revision_id,
            modelo_year=int(ejercicio),
            period=period,
        ),
        values=extracted,
        warnings=warnings,
        extraction_profile_id=f"modelo-{modelo}-declaracion-pdf",
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
            "modelo-130-actividad-economica-ingresos-cumulative": Decimal("10000"),
            "modelo-130-actividad-economica-ingresos-taxable-base-cumulative": Decimal("0"),
            "modelo-130-actividad-economica-rendimiento-neto-cumulative": Decimal("0"),
            "modelo-130-actividad-economica-retenciones-cumulative": Decimal("0"),
            "modelo-130-actividad-economica-gastos-cumulative": Decimal("4000"),
            "modelo-130-resultados-negativos-anteriores": Decimal("0"),
            "modelo-130-pagos-fraccionados-anteriores": Decimal("250"),
        },
    )

    assert verdict.registry_snapshot_id == "130:2019-y-siguientes:2025:1T"
    # The coverage-gated contract plus the exhaustive reconcile-when-present
    # contract both apply; the reconcile-when-present casillas (15,
    # saldo-negativo) are excluded from the coverage denominator, so a clean
    # filing that prints them stays VERIFIED at coverage 1.0 with no discrepancy.
    assert verdict.verification_expectation_ids == (
        "modelo-130-calculation-verification",
        "modelo-130-2019-y-siguientes-reconcile-when-present",
    )
    assert verdict.status is VerificationStatus.VERIFIED
    assert verdict.coverage == 1.0
    assert verdict.discrepancies == ()


def test_reconcile_when_present_casilla_surfaces_a_present_divergence() -> None:
    """A reconcile-when-present casilla is value-reconciled when the filing prints it.

    Casilla ``15`` (M130 saldo positivo period cap) is enrolled in the exhaustive
    reconcile-when-present contract, not the coverage-gated one. The clean filing
    above prints ``15 = 0`` and stays VERIFIED. Here the same filing prints a
    divergent ``15``; the reconcile-when-present class must surface the
    filed-vs-computed discrepancy and drive NEEDS_REVIEW - proving the class
    actually reconciles rather than silently ignoring the casilla.
    """
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
            ("12", Decimal("600.00")),
            ("13", Decimal("0")),
            ("14", Decimal("600.00")),
            ("15", Decimal("5000.00")),
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
            "modelo-130-actividad-economica-ingresos-cumulative": Decimal("10000"),
            "modelo-130-actividad-economica-ingresos-taxable-base-cumulative": Decimal("0"),
            "modelo-130-actividad-economica-rendimiento-neto-cumulative": Decimal("0"),
            "modelo-130-actividad-economica-retenciones-cumulative": Decimal("0"),
            "modelo-130-actividad-economica-gastos-cumulative": Decimal("4000"),
            "modelo-130-resultados-negativos-anteriores": Decimal("0"),
            "modelo-130-pagos-fraccionados-anteriores": Decimal("250"),
        },
    )

    assert verdict.status is VerificationStatus.NEEDS_REVIEW
    diverged = {d.casilla_id for d in verdict.discrepancies}
    assert _casilla_id("15") in diverged


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
            "modelo-130-actividad-economica-ingresos-cumulative": Decimal("10000"),
            "modelo-130-actividad-economica-ingresos-taxable-base-cumulative": Decimal("0"),
            "modelo-130-actividad-economica-rendimiento-neto-cumulative": Decimal("0"),
            "modelo-130-actividad-economica-retenciones-cumulative": Decimal("0"),
            "modelo-130-actividad-economica-gastos-cumulative": Decimal("4000"),
            "modelo-130-resultados-negativos-anteriores": Decimal("0"),
        },
    )

    assert verdict.status is VerificationStatus.NEEDS_REVIEW
    assert verdict.discrepancies[0].casilla_id == _M130_RESULTADO_CASILLA


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

    assert verdict.registry_snapshot_id == "115:2019-y-siguientes:2026:1T"
    assert verdict.verification_expectation_ids == ("modelo-115-calculation-verification",)
    assert verdict.status is VerificationStatus.VERIFIED
    assert verdict.coverage == 1.0
    assert verdict.discrepancies == ()


def test_verify_declaracion_uses_modelo_123_current_registry_snapshot() -> None:
    filing = _build_filing(
        modelo="123",
        period="1T",
        ejercicio="2026",
        registry_revision_id="2024-y-siguientes",
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

    assert verdict.registry_snapshot_id == "123:2024-y-siguientes:2026:1T"
    assert verdict.verification_expectation_ids == ("modelo-123-calculation-verification",)
    assert verdict.status is VerificationStatus.VERIFIED
    assert verdict.coverage == 1.0
    assert verdict.discrepancies == ()


def test_verify_declaracion_uses_modelo_123_historical_registry_snapshot() -> None:
    filing = _build_filing(
        modelo="123",
        period="1T",
        ejercicio="2023",
        registry_revision_id="2019-2023",
        values=(
            ("01", Decimal("2")),
            ("02", Decimal("1000.25")),
            ("03", Decimal("190.05")),
            ("04", Decimal("0")),
            ("05", Decimal("7.50")),
            ("06", Decimal("197.55")),
            ("07", Decimal("12.25")),
            ("08", Decimal("185.30")),
        ),
    )

    verdict = verify_declaracion(filing)

    assert verdict.registry_snapshot_id == "123:2019-2023:2023:1T"
    assert verdict.verification_expectation_ids == ("modelo-123-2019-calculation-verification",)
    assert verdict.status is VerificationStatus.VERIFIED
    assert verdict.coverage == 1.0
    assert verdict.discrepancies == ()


def test_verify_declaracion_refuses_snapshot_ref_revision_divergence() -> None:
    filing = _build_filing(
        values=(("01", Decimal("10000")),),
        registry_revision_id="wrong-revision",
    )

    with pytest.raises(VerificationError) as raised:
        verify_declaracion(filing)

    error = raised.value
    assert error.translated_message == "application.verification.errors.registry_snapshot_ref_mismatch"
    assert error.context == {
        "modelo": "130",
        "period": "2025 1T",
        "observed_ref": "130:wrong-revision:2025:1T",
        "resolved_ref": "130:2019-y-siguientes:2025:1T",
    }


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
            "modelo-130-actividad-economica-retenciones-cumulative",
            "modelo-130-resultados-negativos-anteriores",
        ),
        "count": 5,
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


def test_verify_declaracion_reports_zero_grounding_fraction_when_none_declared() -> None:
    """R1: a revision with no ``externally_grounded_casilla_ids`` reports a zero fraction.

    Modelo 130's verification expectations declare no
    ``externally_grounded_casilla_ids`` (per the verification-power research,
    M130 carries zero per-casilla external-oracle grounding - its
    ``workbook_parity_refs`` are whole-workbook fixture parity, not a
    per-casilla oracle). The verdict must report an empty
    ``externally_grounded_casilla_ids`` tuple and a ``0.0``
    ``independently_grounded_fraction`` rather than fabricating a grounding
    claim the registry never declared.
    """
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
            "modelo-130-actividad-economica-ingresos-cumulative": Decimal("10000"),
            "modelo-130-actividad-economica-ingresos-taxable-base-cumulative": Decimal("0"),
            "modelo-130-actividad-economica-rendimiento-neto-cumulative": Decimal("0"),
            "modelo-130-actividad-economica-retenciones-cumulative": Decimal("0"),
            "modelo-130-actividad-economica-gastos-cumulative": Decimal("4000"),
            "modelo-130-resultados-negativos-anteriores": Decimal("0"),
            "modelo-130-pagos-fraccionados-anteriores": Decimal("250"),
        },
    )

    assert verdict.status is VerificationStatus.VERIFIED
    assert verdict.externally_grounded_casilla_ids == ()
    assert verdict.independently_grounded_fraction == 0.0


def test_m100_2025_registry_policy_reports_independently_grounded_fraction() -> None:
    """R1: the M100/2025 registry-declared grounding tier folds to a non-zero fraction.

    ``verify_declaracion`` cannot currently drive a full M100/2025
    calculation end to end: the 2025 revision folds two relation-sourced
    bindings (``renta-2025-rel-130-pagos-fraccionados`` /
    ``renta-2025-rel-131-pagos-fraccionados``) that the verify wrapper has no
    parameter to supply - it forwards only ``binding_values`` to
    ``calculate_registry_snapshot``, never ``relation_values``. That gap is
    pre-existing and orthogonal to R1 (verification grounding-tier
    transparency); widening ``verify_declaracion``'s public signature to
    close it is out of this Step's scope.

    This test instead exercises the exact computation ``verify_declaracion``
    performs once ``status``/``coverage`` are finalised -
    ``policy.externally_grounded_casilla_ids & reconciled_casilla_ids`` and
    the resulting fraction - directly against a real, fully-resolved
    M100/2025 ``RegistryCalculationResult``. The binding/relation/date inputs
    are the same set that
    ``test_modelo_100_registry_scenarios_cover_direct_estimation_modes_and_payments``
    (``domain/calculations/registry/tests/test_registry_scenarios.py``)
    already proves calculates cleanly for this revision. The assertion is not
    a hand-computed number: it is the live registry declaration
    (``externally_grounded_casilla_ids`` on the 2025 cuota-chain and
    reconcile-when-present verification expectations, derived from the
    bundled Renta WEB Open replay corpus) intersected against the live
    policy fold.
    """
    snapshot = resources().modelos.authority.snapshot("100", filing_year=2025, period="0A")

    def _m100_cid(value: str) -> CasillaId:
        return validated_casilla_id(value, surface="test_m100_2025 fixture")

    inputs = {
        _m100_cid(casilla_id): value
        for casilla_id, value in {
            "0171": Decimal("1000.00"),
            "0172": Decimal("200.00"),
            "0181": Decimal("300.00"),
            "0219": Decimal("50.00"),
            "0225": Decimal("10.00"),
            "0236": Decimal("5.00"),
            "0232": Decimal("1.00"),
            "0233": Decimal("2.00"),
            "0234": Decimal("3.00"),
            "0237": Decimal("4.00"),
            "0592": Decimal("1.00"),
            "0593": Decimal("2.00"),
            "0594": Decimal("3.00"),
            "0153": Decimal("6.00"),
            "0599": Decimal("7.00"),
            "0600": Decimal("8.00"),
            "0601": Decimal("9.00"),
            "0602": Decimal("10.00"),
            "0603": Decimal("11.00"),
            "0605": Decimal("12.00"),
            "0606": Decimal("13.00"),
        }.items()
    }
    binding_values = {
        "renta-2025-modelo-100-estimacion-directa-es-normal": Decimal("1"),
        # The fixture exercises the estimación directa "normal" regime branch
        # (the sibling binding above), which the rendimiento-neto formula only
        # reaches when the taxpayer has economic activity; keep the two
        # bindings consistent so the es-normal input is not dead.
        "renta-2025-profile-has-economic-activity": Decimal("1"),
        "renta-2025-modelo-184-atribucion-actividades-economicas": Decimal("0"),
        "renta-2025-profile-declaration-type": Decimal("1"),
        "renta-2025-profile-family-minor-children-in-unit": Decimal("0"),
        "renta-2025-profile-marriage-full-year": Decimal("0"),
        "renta-2025-profile-marriage-month-start": Decimal("0"),
        "renta-2025-profile-marriage-month-end": Decimal("0"),
        "renta-2025-base-liquidable-negativa-general-anterior": Decimal("0"),
        "renta-2025-modelo-111-retenciones-periodicas": Decimal("4.00"),
        "renta-2025-modelo-123-retenciones-periodicas": Decimal("5.00"),
        "renta-2025-profile-unidad-familiar-otros-miembros-base": Decimal("0"),
        "renta-2025-profile-madrid-nacimiento-adopcion-eligible-count": Decimal("0"),
        # Childless profile: Art. 58/61 LIRPF mínimo por descendientes aggregate
        # is zero.
        "renta-2025-profile-minimo-descendientes-estatal": Decimal("0"),
        # Parte autonómica: non-Madrid profile mirrors the estatal zero.
        "renta-2025-profile-minimo-descendientes-autonomico": Decimal("0"),
    }

    result = calculate_registry_snapshot(
        snapshot,
        inputs=inputs,
        date_context={"filing_period": date(2025, 12, 31)},
        binding_values=binding_values,
        enum_binding_values={"renta-2025-profile-tax-residence-ccaa": "madrid"},
        relation_values={
            "renta-2025-rel-130-pagos-fraccionados": Decimal("45.00"),
            "renta-2025-rel-131-pagos-fraccionados": Decimal("55.00"),
        },
        date_binding_values={"renta-2025-profile-taxpayer-birth-date": date(1985, 6, 15)},
    )
    assert result.values, "the M100/2025 calculation must close before the policy fold is meaningful"

    # This is the identical computation `_verify.py` performs after
    # status/coverage are finalised - proven here against the real registry
    # snapshot rather than re-derived from a synthetic policy fixture.
    policy = snapshot.verification_policy()
    reconciled_casilla_ids = policy.computed_casilla_ids | policy.reconcile_when_present_casilla_ids
    externally_grounded = policy.externally_grounded_casilla_ids & reconciled_casilla_ids
    independently_grounded_fraction = (
        len(externally_grounded) / len(reconciled_casilla_ids) if reconciled_casilla_ids else 0.0
    )

    assert externally_grounded == {
        _m100_cid("0519"),
        _m100_cid("0520"),
        _m100_cid("0610"),
        _m100_cid("0670"),
    }
    assert independently_grounded_fraction > 0.0


class TestVerdictJsonRoundTrip:
    """JSON serialisation invariants for
    :class:`cadrumo.application.verification.VerificationVerdict`.
    """

    def test_verdict_is_json_serialisable(self) -> None:
        """Verify a verdict survives ``model_dump_json`` round-trip.

        The ``period`` field serialises as ``{"filing_year": 2025, "code": "1T"}``
        (the canonical :class:`~cadrumo.core.Period` JSON shape) and is
        reconstituted to the same :class:`~cadrumo.core.Period` on reload.
        """
        verdict = VerificationVerdict(
            modelo="130",
            period=Period.from_year_and_code(2025, "1T"),
            registry_snapshot_id="130:2019-y-siguientes:2025:1T",
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
