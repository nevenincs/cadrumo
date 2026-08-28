"""Shared builders for IVA compensation history tests."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from functools import cache
from typing import Literal

from pydantic import AnyHttpUrl

from ....adapters.outbound.aeat.sede import (
    IVA_COMPENSATION_WALLET_URL,
    FiledDeclaracionArtefact,
    FiledDeclaracionObservation,
    IvaCompensationWalletObservation,
    IvaCompensationWalletRow,
    ObservedCasillaValue,
)
from ....core import (
    CasillaId,
    CasillaValueKind,
    IvaCompensationStateProvenance,
    Period,
    RegistryAuthorityGrade,
    validated_casilla_id,
)
from ....core.resources import bundled_path
from ....domain.calculations.registry.schema import RegistrySnapshot
from ....domain.calculations.registry.snapshot import build_snapshot
from ....domain.iva_compensation import IvaCompensationPeriodState
from ....tests.registry_tree import bundled_registry_tree

#: A checksum-valid synthetic NIF. ``IvaCompensationPeriodState.taxpayer_nif``
#: is a ``SubjectTaxId``, so a placeholder label is refused at the boundary
#: and the fixture must carry a real identifier shape.
_TAXPAYER_REF = "12345678Z"


_M303_COMPENSACION_PENDIENTE_ANTERIORES_CASILLA: CasillaId = validated_casilla_id(
    "iva.compensacion-pendiente-periodos-anteriores"
)
_M303_COMPENSACION_APLICADA_CASILLA: CasillaId = validated_casilla_id("iva.compensacion-aplicada-periodo")
_M303_POSTERIOR_CASILLA: CasillaId = validated_casilla_id("iva.compensacion-pendiente-periodos-posteriores")
_M303_RESULTADO_CASILLA: CasillaId = validated_casilla_id("iva.resultado")
_M303_RESULTADO_FINAL_CASILLA: CasillaId = validated_casilla_id("71")
_M303_GENERADA_CASILLA: CasillaId = validated_casilla_id("iva.compensacion-generada-periodo")
_M303_DISPONIBLE_CASILLA: CasillaId = validated_casilla_id("iva.compensacion-disponible-fin-periodo")
_M303_CUOTA_DEVENGADA_TOTAL_CASILLA: CasillaId = validated_casilla_id("iva.cuota-devengada-total")
_M303_CUOTA_DEDUCIBLE_TOTAL_CASILLA: CasillaId = validated_casilla_id("iva.cuota-deducible-total")
_M303_RESULTADO_REGIMEN_GENERAL_CASILLA: CasillaId = validated_casilla_id("iva.resultado-regimen-general")
_M390_COMPENSACION_ULTIMO_PERIODO_CASILLA: CasillaId = validated_casilla_id("iva.anual.compensacion-ultimo-periodo-97")
_M390_COMPENSACION_GENERADA_EJERCICIO_NO_97_CASILLA: CasillaId = validated_casilla_id(
    "iva.anual.compensacion-generada-ejercicio-no-97"
)
_M303_PRINTED_PERIOD_RESULT_REFERENCE_CASILLA: CasillaId = validated_casilla_id("69")
_M303_PRINTED_COMPENSATION_REFERENCE_CASILLA: CasillaId = validated_casilla_id("87")
_M390_PRINTED_LAST_PERIOD_COMPENSATION_REFERENCE_CASILLA: CasillaId = validated_casilla_id("97")

#: The ejercicio these fixtures summarise. Modelo 390 is annual, so the
#: ejercicio must be one AEAT has published a design for; the annual instrument
#: for a given ejercicio appears late in that same year.
_M390_EJERCICIO = 2025

_BOX_97_BINDING = "modelo-390-prev-303-compensacion-ultimo-periodo"
_BOX_662_BINDING = "modelo-390-prev-303-compensacion-generada-ejercicio-no-97"


@cache
def _modelo_390_annual_snapshot() -> RegistrySnapshot:
    """Build a CALCULATION-grade snapshot directly, bypassing filing-grade admission.

    Modelo 390 carries a real fichero-BOE layout on every revision, so this
    succeeds; it deliberately does not go through
    :class:`~domain.calculations.registry.ValidatedRegistryAuthority`, whose
    ``.load()`` validates the entire registry tree (including modelos with no
    export layout at all) and currently refuses unconditionally as a result.
    """
    modelos, catalogues = bundled_registry_tree()
    modelo = next(candidate for candidate in modelos if candidate.id == "390")
    return build_snapshot(
        modelo,
        catalogues,
        source_root=bundled_path(),
        filing_year=_M390_EJERCICIO,
        period="0A",
        grade=RegistryAuthorityGrade.CALCULATION,
    )


def _state(
    *,
    filing_year: int,
    period: str,
    generated: Decimal = Decimal("0.00"),
    applied: Decimal = Decimal("0.00"),
    available: Decimal | None = None,
) -> IvaCompensationPeriodState:
    return IvaCompensationPeriodState(
        provenance=IvaCompensationStateProvenance.APP_FILING,
        taxpayer_nif=_TAXPAYER_REF,
        filing_year=filing_year,
        period=Period.from_year_and_code(filing_year, period),
        presented_at=datetime(filing_year + 1, 1, 20, 12, 0, tzinfo=UTC),
        prior_pending_amount=None,
        applied_amount=applied,
        pending_for_later_amount=None,
        period_result_amount=None,
        final_result_amount=None,
        generated_amount=generated,
        available_end_amount=generated if available is None else available,
        source_observation_key=f"303:{filing_year}:{period}:EXP",
    )


def _wallet(amount: Decimal, *, generation_year: int = 2022) -> IvaCompensationWalletObservation:
    return IvaCompensationWalletObservation(
        taxpayer_nif=_TAXPAYER_REF,
        authenticated_identity=_TAXPAYER_REF,
        target_year=2026,
        target_period=Period.from_year_and_code(2026, "2T"),
        rows=(
            IvaCompensationWalletRow(
                generation_year=generation_year,
                generation_period=Period.from_year_and_code(generation_year, "4T"),
                generated_amount=amount,
                applied_amount=Decimal("0"),
                pending_amount=amount,
                raw_label=f"{generation_year} 4T",
            ),
        ),
        total_pending=amount,
        source_url=AnyHttpUrl(IVA_COMPENSATION_WALLET_URL),
        captured_at=datetime(2026, 5, 19, 10, 0, tzinfo=UTC),
        raw_sha256="a" * 64,
    )


def _filed_observation(modelo: str) -> FiledDeclaracionObservation:
    return FiledDeclaracionObservation(
        modelo=modelo,
        ejercicio=2024,
        period=Period.from_year_and_code(2024, "4T"),
        expediente_id="202410013522456T",
        status="filed",
        presented_at=datetime(2025, 1, 20, 12, 0, tzinfo=UTC),
        authenticated_identity=_TAXPAYER_REF,
        artefacts=(
            FiledDeclaracionArtefact(
                kind="register_row",
                source_url=AnyHttpUrl("https://example.test/expedientes/test"),
                content_type="text/html",
                byte_count=0,
                sha256="a" * 64,
                captured_at=datetime(2025, 1, 20, 12, 0, tzinfo=UTC),
            ),
        ),
    )


def _filed_303_compensation_observation(
    *,
    filing_year: int,
    period: str,
    resultado: Decimal,
    prior_pending: Decimal = Decimal("0.00"),
    applied: Decimal = Decimal("0.00"),
    posterior: Decimal = Decimal("0.00"),
    final_result: Decimal | None = None,
) -> FiledDeclaracionObservation:
    resolved_final_result = resultado if final_result is None else final_result
    return _filed_observation(modelo="303").model_copy(
        update={
            "ejercicio": filing_year,
            "period": Period.from_year_and_code(filing_year, period),
            "expediente_id": f"{filing_year}303{period}000001",
            "presented_at": datetime(filing_year + 1, 1, 20, 12, 0, tzinfo=UTC),
            "casillas": (
                ObservedCasillaValue(
                    casilla_id=_M303_COMPENSACION_PENDIENTE_ANTERIORES_CASILLA,
                    value=str(prior_pending),
                    value_kind=CasillaValueKind.NUMERIC,
                    source_artefact_kind="submitted_file",
                    source_locator=f"submitted-file:303:{period}:110",
                    confidence=1.0,
                ),
                ObservedCasillaValue(
                    casilla_id=_M303_COMPENSACION_APLICADA_CASILLA,
                    value=str(applied),
                    value_kind=CasillaValueKind.NUMERIC,
                    source_artefact_kind="submitted_file",
                    source_locator=f"submitted-file:303:{period}:78",
                    confidence=1.0,
                ),
                ObservedCasillaValue(
                    casilla_id=_M303_RESULTADO_CASILLA,
                    value=str(resultado),
                    value_kind=CasillaValueKind.NUMERIC,
                    source_artefact_kind="submitted_file",
                    source_locator=f"submitted-file:303:{period}:69",
                    confidence=1.0,
                ),
                ObservedCasillaValue(
                    casilla_id=_M303_POSTERIOR_CASILLA,
                    value=str(posterior),
                    value_kind=CasillaValueKind.NUMERIC,
                    source_artefact_kind="submitted_file",
                    source_locator=f"submitted-file:303:{period}:87",
                    confidence=1.0,
                ),
                ObservedCasillaValue(
                    casilla_id=_M303_RESULTADO_FINAL_CASILLA,
                    value=str(resolved_final_result),
                    value_kind=CasillaValueKind.NUMERIC,
                    source_artefact_kind="submitted_file",
                    source_locator=f"submitted-file:303:{period}:71",
                    confidence=1.0,
                ),
            ),
        },
    )


def _filed_390_observation(
    *,
    last_period_compensation: Decimal,
    generated_not_in_last_period: Decimal,
) -> FiledDeclaracionObservation:
    return FiledDeclaracionObservation(
        modelo="390",
        ejercicio=2025,
        period=Period.from_year_and_code(2025, "0A"),
        expediente_id="200039000000001Z",
        status="filed",
        presented_at=datetime(2026, 1, 30, 12, 0, tzinfo=UTC),
        authenticated_identity=_TAXPAYER_REF,
        artefacts=(
            FiledDeclaracionArtefact(
                kind="submitted_file",
                source_url=AnyHttpUrl("https://example.test/390/submitted-file/test"),
                content_type="text/plain",
                byte_count=0,
                sha256="b" * 64,
                captured_at=datetime(2026, 1, 30, 12, 0, tzinfo=UTC),
            ),
        ),
        casillas=(
            ObservedCasillaValue(
                casilla_id=_M390_COMPENSACION_ULTIMO_PERIODO_CASILLA,
                value=str(last_period_compensation),
                value_kind=CasillaValueKind.NUMERIC,
                source_artefact_kind="submitted_file",
                source_locator="submitted-file:390:97",
                confidence=1.0,
            ),
            ObservedCasillaValue(
                casilla_id=_M390_COMPENSACION_GENERADA_EJERCICIO_NO_97_CASILLA,
                value=str(generated_not_in_last_period),
                value_kind=CasillaValueKind.NUMERIC,
                source_artefact_kind="submitted_file",
                source_locator="submitted-file:390:662",
                confidence=1.0,
            ),
        ),
    )


_M303PrintedNumberSourceKind = Literal["submitted_file", "justificante_pdf"]

_M303_PRINTED_NUMBER_REFERENCE_CASES: tuple[tuple[_M303PrintedNumberSourceKind, str], ...] = (
    ("submitted_file", "submitted-file:casilla-69"),
    ("justificante_pdf", "justificante-pdf:casilla-69"),
)
