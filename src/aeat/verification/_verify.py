"""Verification orchestrator: DeclaracionFiling → VerificationVerdict."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from ..declaracion import DeclaracionFiling
from ..formulas import Engine
from ..formulas._ledger import Discrepancy
from ..formulas._ruleset import Ruleset
from ..i18n import Translatable
from ._schema import (
    ClassifiedDiscrepancy,
    DiscrepancyCause,
    VerificationStatus,
    VerificationVerdict,
)

_DEFAULT_TOLERANCE = Decimal("0.01")

# Extractor-warning codes that flag low-confidence extraction.
_UNRELIABLE_WARNING_CODES: frozenset[str] = frozenset(
    {
        "bbox-fallback",
        "ambiguous-label",
        "value-unparseable",
        "casilla-not-found",  # audit H1 — missing casillas also down-rank verdict
    }
)


def verify_declaracion(
    declaracion: DeclaracionFiling,
    *,
    ruleset: Ruleset | None,
    tolerance: Decimal = _DEFAULT_TOLERANCE,
) -> VerificationVerdict:
    """Compare the printed casilla values against engine-derived ones.

    Args:
        declaracion: The parsed filing from :func:`aeat.declaracion.parse_declaracion`.
        ruleset: The formula ruleset to audit against; ``None`` → verdict is
            :attr:`VerificationStatus.UNVERIFIABLE`.
        tolerance: Maximum absolute delta between printed and computed values
            to still count as a match. Defaults to 0.01 (one cent).

    Returns:
        A frozen :class:`VerificationVerdict` with status + classified
        discrepancies + trilingual narrative + timestamp.
    """
    if ruleset is None:
        return _unverifiable_verdict(declaracion)

    provided: dict[str, Decimal] = {}
    for value in declaracion.values:
        if isinstance(value.printed_value, Decimal):
            provided[value.casilla_id] = value.printed_value

    engine = Engine()
    report = engine.audit_against(
        ruleset=ruleset,
        provided=provided,
        tolerance=tolerance,
    )

    unreliable_ids = {
        w.casilla_id for w in declaracion.warnings if w.casilla_id is not None and w.code in _UNRELIABLE_WARNING_CODES
    }
    ruleset_casillas = {c.casilla_id for c in ruleset.casillas}

    classified = tuple(
        _classify_discrepancy(
            d,
            unreliable_ids=unreliable_ids,
            ruleset_casillas=ruleset_casillas,
            tolerance=tolerance,
        )
        for d in report.discrepancies
    )

    coverage = _compute_coverage(declaracion, ruleset_casillas)
    status = _derive_status(classified, coverage)
    narrative = _compose_narrative(declaracion, status, classified, coverage)

    return VerificationVerdict(
        modelo=declaracion.modelo,
        period=declaracion.period,
        ruleset_id=ruleset.ruleset_id,
        status=status,
        discrepancies=classified,
        coverage=coverage,
        narrative=narrative,
        verified_at=datetime.now(tz=UTC),
    )


def _classify_discrepancy(
    discrepancy: Discrepancy,
    *,
    unreliable_ids: set[str],
    ruleset_casillas: set[str],
    tolerance: Decimal,
) -> ClassifiedDiscrepancy:
    """Assign one of the four cause categories to a raw discrepancy."""
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
            hu=(f"{casilla_id} casilla: az extraktor alacsony magabiztosságúnak jelölte. Ellenőrizd a PDF-et kézzel."),
        )
    elif casilla_id not in ruleset_casillas:
        cause = DiscrepancyCause.UNMODELLED_RULE
        rationale = Translatable(
            es=(f"Casilla {casilla_id}: el ruleset no contempla esta casilla. Se acepta el valor extraído."),
            en=(f"Casilla {casilla_id}: the ruleset has no formula for it. Extracted value accepted as-is."),
            hu=(f"{casilla_id} casilla: a ruleset nem ismeri. A kinyert érték elfogadva."),
        )
    elif abs_delta < 10 * tolerance:
        cause = DiscrepancyCause.ROUNDING
        rationale = Translatable(
            es=f"Casilla {casilla_id}: diferencia dentro del margen de redondeo ({abs_delta} €).",
            en=f"Casilla {casilla_id}: delta within rounding tolerance ({abs_delta} €).",
            hu=f"{casilla_id} casilla: a kerekítési toleranciába esik ({abs_delta} €).",
        )
    else:
        cause = DiscrepancyCause.CORRECTNESS_DIVERGENCE
        rationale = Translatable(
            es=(f"Casilla {casilla_id}: diferencia significativa ({abs_delta} €). Revisa el PDF o el ruleset."),
            en=(f"Casilla {casilla_id}: material divergence ({abs_delta} €). Review the PDF or the ruleset."),
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
    """Fraction of the ruleset's casillas that the extraction supplied."""
    if not ruleset_casillas:
        return 0.0
    provided_ids = {v.casilla_id for v in declaracion.values}
    covered = ruleset_casillas & provided_ids
    return len(covered) / len(ruleset_casillas)


def _derive_status(
    classified: tuple[ClassifiedDiscrepancy, ...],
    coverage: float,
) -> VerificationStatus:
    """Map discrepancies + coverage to a single-word status."""
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
    """Build the trilingual summary string Kent sees after import."""
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
    """Produce the ``UNVERIFIABLE`` verdict when no ruleset is available."""
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
