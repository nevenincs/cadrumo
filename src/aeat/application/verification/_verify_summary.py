"""Tier-S summary-return verification."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from ...adapters.inbound.declaracion import DeclaracionFiling
from ...core.i18n import Translatable
from ...domain.modelos.m347 import MANIFEST_2024, MANIFEST_2025, MANIFEST_2026
from ._schema import ClassifiedDiscrepancy, DiscrepancyCause, VerificationStatus, VerificationVerdict

_DEFAULT_TOLERANCE = Decimal("0.01")
_MANIFESTS = {
    2024: MANIFEST_2024,
    2025: MANIFEST_2025,
    2026: MANIFEST_2026,
}


def verify_modelo_347_summary(
    declaracion: DeclaracionFiling,
    *,
    tolerance: Decimal = _DEFAULT_TOLERANCE,
) -> VerificationVerdict:
    """Verify Modelo 347 per-counterparty detail rows against resumen totals."""
    manifest = _MANIFESTS.get(int(declaracion.ejercicio))
    if manifest is None:
        return _summary_verdict(
            declaracion,
            status=VerificationStatus.UNVERIFIABLE,
            discrepancies=(),
            narrative={
                "es": f"Modelo 347 {declaracion.period}: ejercicio no soportado para verificacion Tier-S.",
                "en": f"Modelo 347 {declaracion.period}: exercise not supported for Tier-S verification.",
                "hu": f"347 modell {declaracion.period}: az ev nem tamogatott Tier-S ellenorzeshez.",
            },
        )

    by_id = {
        value.casilla_id: value.printed_value
        for value in declaracion.values
        if isinstance(value.printed_value, Decimal)
    }
    records = declaracion.modelo_347_records
    expected_count = Decimal(len(records))
    expected_total = sum((record.annual_operation_amount for record in records), Decimal("0.00"))
    expected_cash_count = Decimal(sum(1 for record in records if record.cash_received_amount > Decimal("0.00")))
    expected_cash_total = sum((record.cash_received_amount for record in records), Decimal("0.00"))

    discrepancies: list[ClassifiedDiscrepancy] = []
    _append_if_mismatch(
        discrepancies,
        casilla_id=manifest.summary_count_casilla,
        expected=expected_count,
        actual=by_id.get(manifest.summary_count_casilla),
        tolerance=Decimal("0.00"),
    )
    _append_if_mismatch(
        discrepancies,
        casilla_id=manifest.summary_total_casilla,
        expected=expected_total,
        actual=by_id.get(manifest.summary_total_casilla),
        tolerance=tolerance,
    )
    _append_if_mismatch(
        discrepancies,
        casilla_id=manifest.summary_cash_count_casilla,
        expected=expected_cash_count,
        actual=by_id.get(manifest.summary_cash_count_casilla),
        tolerance=Decimal("0.00"),
    )
    if expected_cash_total != Decimal("0.00") or by_id.get(manifest.summary_cash_total_casilla) is not None:
        _append_if_mismatch(
            discrepancies,
            casilla_id=manifest.summary_cash_total_casilla,
            expected=expected_cash_total,
            actual=by_id.get(manifest.summary_cash_total_casilla),
            tolerance=tolerance,
        )

    status = VerificationStatus.VERIFIED if not discrepancies else VerificationStatus.NEEDS_REVIEW
    return _summary_verdict(
        declaracion,
        status=status,
        discrepancies=tuple(discrepancies),
        narrative=_compose_summary_narrative(declaracion, status, tuple(discrepancies), expected_total),
    )


def _append_if_mismatch(
    discrepancies: list[ClassifiedDiscrepancy],
    *,
    casilla_id: str,
    expected: Decimal,
    actual: Decimal | None,
    tolerance: Decimal,
) -> None:
    actual_value = Decimal("0.00") if actual is None else actual
    if abs(expected - actual_value) <= tolerance:
        return
    delta = actual_value - expected
    discrepancies.append(
        ClassifiedDiscrepancy(
            casilla_id=casilla_id,
            expected=expected,
            actual=actual_value,
            delta=delta,
            cause=DiscrepancyCause.CORRECTNESS_DIVERGENCE,
            cause_rationale={
                "es": (
                    f"Casilla {casilla_id}: el resumen impreso no coincide con "
                    f"la suma de los registros declarados (diferencia {abs(delta)} EUR)."
                ),
                "en": (
                    f"Casilla {casilla_id}: printed summary does not match "
                    f"the sum of declared records (delta {abs(delta)} EUR)."
                ),
                "hu": (
                    f"{casilla_id} casilla: a nyomtatott osszesito nem egyezik "
                    f"a rekordok osszegevel (elteres {abs(delta)} EUR)."
                ),
            },
        )
    )


def _summary_verdict(
    declaracion: DeclaracionFiling,
    *,
    status: VerificationStatus,
    discrepancies: tuple[ClassifiedDiscrepancy, ...],
    narrative: Translatable,
) -> VerificationVerdict:
    return VerificationVerdict(
        modelo=declaracion.modelo,
        period=declaracion.period,
        ruleset_id=None,
        status=status,
        discrepancies=discrepancies,
        coverage=1.0 if declaracion.modelo_347_records else 0.0,
        narrative=narrative,
        verified_at=datetime.now(tz=UTC),
    )


def _compose_summary_narrative(
    declaracion: DeclaracionFiling,
    status: VerificationStatus,
    discrepancies: tuple[ClassifiedDiscrepancy, ...],
    total: Decimal,
) -> Translatable:
    count = len(declaracion.modelo_347_records)
    if status is VerificationStatus.VERIFIED:
        return {
            "es": f"Modelo 347 {declaracion.period}: verificado. {count} declarados suman {total} EUR.",
            "en": f"Modelo 347 {declaracion.period}: verified. {count} declared records sum to {total} EUR.",
            "hu": f"347 modell {declaracion.period}: igazolva. {count} rekord osszesen {total} EUR.",
        }
    return {
        "es": (
            f"Modelo 347 {declaracion.period}: revisar. {len(discrepancies)} diferencias entre registros y resumen."
        ),
        "en": (
            f"Modelo 347 {declaracion.period}: needs review. "
            f"{len(discrepancies)} differences between records and summary."
        ),
        "hu": (
            f"347 modell {declaracion.period}: felulvizsgalat szukseges. "
            f"{len(discrepancies)} elteres a rekordok es az osszesito kozott."
        ),
    }


__all__ = ["verify_modelo_347_summary"]
