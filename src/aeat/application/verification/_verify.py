"""Registry-gated declaration verification boundary.

Parsed declaración verification is filing-grade calculation work. Until
that path is backed by validated registry snapshots, the public entry
point fails closed instead of reaching legacy rulesets.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from typing import Protocol

from ...adapters.inbound.declaracion import DeclaracionFiling
from ...core.i18n import Translatable
from ...core.logging import get_logger
from ._schema import (
    ClassifiedDiscrepancy,
    DiscrepancyCause,
    VerificationStatus,
    VerificationVerdict,
)

_logger = get_logger(__name__)

_DEFAULT_TOLERANCE = Decimal("0.01")
"""Default per-casilla absolute tolerance (one cent) for verdicts."""

_UNRELIABLE_WARNING_CODES: frozenset[str] = frozenset(
    {
        "bbox-fallback",
        "ambiguous-label",
        "value-unparseable",
        "casilla-not-found",
    }
)
"""Extractor warning codes that mark a casilla extraction as low-confidence."""


class _DiscrepancyLike(Protocol):
    casilla_id: str
    computed_value: Decimal
    user_value: Decimal
    delta: Decimal


def verify_declaracion(
    declaracion: DeclaracionFiling,
    *,
    ruleset: object | None,
    tolerance: Decimal = _DEFAULT_TOLERANCE,
) -> VerificationVerdict:
    """Compare the printed casilla values against engine-derived ones.

    Args:
        declaracion: The parsed filing returned by
            :func:`aeat.adapters.inbound.declaracion.parse_declaracion`.
        ruleset: Legacy placeholder argument kept while call sites are
            migrated to registry snapshots.
        tolerance: Maximum absolute delta between printed and computed
            values to still count as a match. Defaults to ``0.01`` (one
            cent).

    Returns:
        A frozen :class:`aeat.application.verification.VerificationVerdict`
        carrying the status, every
        :class:`aeat.application.verification.ClassifiedDiscrepancy`,
        the coverage fraction, a multilingual narrative, and the UTC
        timestamp the verdict was produced.
    """
    _ = (declaracion, ruleset, tolerance)
    raise ValueError(
        "declaracion verification requires a validated registry snapshot; "
        "legacy formula rulesets are disabled",
    )


def _classify_discrepancy(
    discrepancy: _DiscrepancyLike,
    *,
    unreliable_ids: set[str],
    ruleset_casillas: set[str],
    tolerance: Decimal,
) -> ClassifiedDiscrepancy:
    """Assign one of the four :class:`DiscrepancyCause` categories.

    The classifier prefers extraction-unreliability over rounding so that
    a casilla flagged by the extractor is never silently classified as a
    rounding miss. Casillas absent from the ruleset are routed to
    :attr:`DiscrepancyCause.UNMODELLED_RULE` regardless of delta size.
    """
    casilla_id = discrepancy.casilla_id
    delta = discrepancy.delta
    abs_delta = abs(delta)

    rationale: Translatable
    if casilla_id in unreliable_ids:
        cause = DiscrepancyCause.EXTRACTION_UNRELIABLE
        rationale = Translatable(
            es=(
                f"Casilla {casilla_id}: el extractor ha marcado este valor como poco fiable. Revisa manualmente el PDF."
            ),
            en=(f"Casilla {casilla_id}: the extractor flagged this value as low-confidence. Review the PDF manually."),
            ca=(
                f"Casella {casilla_id}: l'extractor ha marcat aquest valor com a poc fiable. "
                "Revisa manualment el PDF."
            ),
            hu=(f"{casilla_id} casilla: az extraktor alacsony magabiztosságúnak jelölte. Ellenőrizd a PDF-et kézzel."),
        )
    elif casilla_id not in ruleset_casillas:
        cause = DiscrepancyCause.UNMODELLED_RULE
        rationale = Translatable(
            es=(f"Casilla {casilla_id}: el ruleset no contempla esta casilla. Se acepta el valor extraído."),
            en=(f"Casilla {casilla_id}: the ruleset has no formula for it. Extracted value accepted as-is."),
            ca=(f"Casella {casilla_id}: el ruleset no contempla aquesta casella. S'accepta el valor extret."),
            hu=(f"{casilla_id} casilla: a ruleset nem ismeri. A kinyert érték elfogadva."),
        )
    elif abs_delta < 10 * tolerance:
        cause = DiscrepancyCause.ROUNDING
        rationale = Translatable(
            es=f"Casilla {casilla_id}: diferencia dentro del margen de redondeo ({abs_delta} €).",
            en=f"Casilla {casilla_id}: delta within rounding tolerance ({abs_delta} €).",
            ca=f"Casella {casilla_id}: diferència dins del marge d'arrodoniment ({abs_delta} €).",
            hu=f"{casilla_id} casilla: a kerekítési toleranciába esik ({abs_delta} €).",
        )
    else:
        cause = DiscrepancyCause.CORRECTNESS_DIVERGENCE
        rationale = Translatable(
            es=(f"Casilla {casilla_id}: diferencia significativa ({abs_delta} €). Revisa el PDF o el ruleset."),
            en=(f"Casilla {casilla_id}: material divergence ({abs_delta} €). Review the PDF or the ruleset."),
            ca=(f"Casella {casilla_id}: diferència significativa ({abs_delta} €). Revisa el PDF o el ruleset."),
            hu=(f"{casilla_id} casilla: jelentős eltérés ({abs_delta} €). Ellenőrizd a PDF-et vagy a ruleset-et."),
        )

    return ClassifiedDiscrepancy(
        casilla_id=casilla_id,
        expected=discrepancy.computed_value,
        actual=discrepancy.user_value,
        delta=delta,
        cause=cause,
        cause_rationale=rationale,
    )


def _compute_coverage(
    declaracion: DeclaracionFiling,
    ruleset_casillas: set[str],
) -> float:
    """Return the fraction of ruleset casillas the extraction supplied.

    Returns ``0.0`` when the ruleset itself defines no casillas; this
    keeps the downstream coverage threshold in :func:`_derive_status`
    well-defined.
    """
    if not ruleset_casillas:
        return 0.0
    provided_ids = {v.casilla_id for v in declaracion.values}
    covered = ruleset_casillas & provided_ids
    return len(covered) / len(ruleset_casillas)


def _derive_status(
    classified: tuple[ClassifiedDiscrepancy, ...],
    coverage: float,
) -> VerificationStatus:
    """Map discrepancies and coverage onto a :class:`VerificationStatus`.

    Returns :attr:`VerificationStatus.NEEDS_REVIEW` when any discrepancy
    has a blocking cause (extraction-unreliable or
    correctness-divergence) or when ruleset coverage drops below 30%;
    otherwise :attr:`VerificationStatus.VERIFIED`.
    """
    blocking = {
        DiscrepancyCause.CORRECTNESS_DIVERGENCE,
        DiscrepancyCause.EXTRACTION_UNRELIABLE,
    }
    if any(c.cause in blocking for c in classified):
        return VerificationStatus.NEEDS_REVIEW
    if coverage < 0.3:
        return VerificationStatus.NEEDS_REVIEW
    return VerificationStatus.VERIFIED


def _compose_narrative(
    declaracion: DeclaracionFiling,
    status: VerificationStatus,
    classified: tuple[ClassifiedDiscrepancy, ...],
    coverage: float,
) -> Translatable:
    """Build the multilingual summary string the operator sees after import.

    The narrative collapses the verdict into one sentence per supported
    UI language and embeds the coverage percentage and discrepancy count
    so the operator can decide whether to drill into the classified list.
    """
    coverage_pct = round(coverage * 100)
    n_discrepancies = len(classified)
    modelo = declaracion.modelo
    period = declaracion.period

    if status is VerificationStatus.VERIFIED:
        return {
            "es": (
                f"Modelo {modelo} {period}: verificado. Cobertura {coverage_pct}%. "
                f"{n_discrepancies} discrepancias no bloqueantes (redondeo / reglas no modeladas)."
            ),
            "en": (
                f"Modelo {modelo} {period}: verified. Coverage {coverage_pct}%. "
                f"{n_discrepancies} non-blocking discrepancies (rounding / unmodelled rules)."
            ),
            "hu": (
                f"{modelo} modell {period}: igazolva. Lefedettség {coverage_pct}%. "
                f"{n_discrepancies} nem blokkoló eltérés (kerekítés / nem modellezett szabályok)."
            ),
        }
    return {
        "es": (
            f"Modelo {modelo} {period}: revisar. Cobertura {coverage_pct}%. "
            f"{n_discrepancies} discrepancias — revisa la lista clasificada."
        ),
        "en": (
            f"Modelo {modelo} {period}: needs review. Coverage {coverage_pct}%. "
            f"{n_discrepancies} discrepancies — inspect the classified list."
        ),
        "hu": (
            f"{modelo} modell {period}: felülvizsgálat szükséges. Lefedettség {coverage_pct}%. "
            f"{n_discrepancies} eltérés — nézd át a besorolt listát."
        ),
    }


def _unverifiable_verdict(declaracion: DeclaracionFiling) -> VerificationVerdict:
    """Return the canonical
    :attr:`VerificationStatus.UNVERIFIABLE` verdict.

    Used when no ruleset is registered for the filing's
    ``(modelo, período)`` pair; the verdict carries an empty discrepancy
    tuple, zero coverage, and a multilingual explanatory narrative.
    """
    return VerificationVerdict(
        modelo=declaracion.modelo,
        period=declaracion.period,
        ruleset_id=None,
        status=VerificationStatus.UNVERIFIABLE,
        discrepancies=(),
        coverage=0.0,
        narrative={
            "es": (
                f"Modelo {declaracion.modelo} {declaracion.period}: no hay ruleset registrado; no se puede verificar."
            ),
            "en": (
                f"Modelo {declaracion.modelo} {declaracion.period}: no ruleset registered; verification unavailable."
            ),
            "hu": (
                f"{declaracion.modelo} modell {declaracion.period}: "
                "nincs ruleset regisztrálva; az igazolás nem elérhető."
            ),
        },
        verified_at=datetime.now(tz=UTC),
    )


__all__ = ["verify_declaracion"]
