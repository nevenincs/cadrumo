"""Modelo 100 settlement-completeness ADVISORY predicate (no-silent-under-declaration).

M100 carried no settlement-completeness verify predicate on any revision, so a
positive-income filer whose IRPF liability resolved to zero was granted
``verificado_completo`` with zero findings — the silent under-declaration class
that the M200 base-determination and M131 pago-fraccionado advisories
already guard. This module pins the M100 2024/2025 guard:
``implies_nonzero(["0500", "0595"])`` — when base liquidable general (0500) is
strictly positive, the cuota resultante de la autoliquidación (0595, the
liability BEFORE pagos a cuenta) must be non-zero.

The consequent is 0595 (the liability), NOT the cuota diferencial (0610) or the
resultado (0670): those legitimately resolve to zero / negative for a filer
whose retenciones and pagos a cuenta cover the liability (the dominant employee
case), so guarding them would false-fire on the majority of returns. The
implication is strictly-positive in the antecedent, so loss / zero-general-base
/ savings-only filers never fire.

Semantics are derived from the ``implies_nonzero`` material-implication
contract (antecedent > 0 AND consequent == 0 → fire), never from any registry
formula output, and the registration assertions read the loaded snapshot — no
hand-computed Decimal, no tautology. Real registry authority; no mocks.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from ....core import CasillaId, validated_casilla_id
from ....domain.calculations.registry.authority import bundled_authority
from ....domain.calculations.registry.schema_verification import VerificationPredicateDefinition
from ....domain.deadlines import IVARegime, TaxpayerProfile
from ....domain.modelos import (
    ModeloVerificationFindingKind,
    ModeloVerificationFindingSeverity,
)
from .._verification_actions import (
    _evaluate_advisory_predicate_fires,
    _evaluate_verification_predicates,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_EXPRESSION = 'implies_nonzero(["0500", "0595"])'
_PREDICATE_ID_SUFFIX = "cuota-resultante-determinada-cuando-base-liquidable-general-positiva"
_BASE_LIQUIDABLE_GENERAL: CasillaId = validated_casilla_id("0500", surface="m100 settlement advisory test")
_CUOTA_RESULTANTE: CasillaId = validated_casilla_id("0595", surface="m100 settlement advisory test")


def _profile() -> TaxpayerProfile:
    return TaxpayerProfile(
        tax_id="X1234567L",
        iva_regime=IVARegime.GENERAL,
        has_employees=False,
        pays_rent_with_retencion=False,
        does_intracomunitario=False,
        bienes_extranjero_above_threshold=False,
    )


def _predicate() -> VerificationPredicateDefinition:
    return VerificationPredicateDefinition(
        predicate_id=f"modelo-100-2024-{_PREDICATE_ID_SUFFIX}",
        legal_refs=("ley-35-2006:art-50", "ley-35-2006:art-63", "ley-35-2006:art-79"),
        expression=_EXPRESSION,
        finding_kind="ADVISORY",
    )


# ---------------------------------------------------------------------------
# Predicate semantics (derived from implies_nonzero, not from a formula)
# ---------------------------------------------------------------------------


def test_advisory_fires_when_base_positive_and_cuota_zero() -> None:
    """Positive base liquidable general + zero cuota resultante → advisory fires.

    The genuine silent under-declaration: positive taxable general base but the
    return computes no tax liability.
    """
    values: dict[CasillaId, Decimal] = {
        _BASE_LIQUIDABLE_GENERAL: Decimal("18000"),
        _CUOTA_RESULTANTE: Decimal("0"),
    }
    assert _evaluate_advisory_predicate_fires(_EXPRESSION, values) is True


def test_advisory_fires_when_base_positive_and_cuota_absent() -> None:
    """Positive base + absent cuota (reads as Decimal(0)) → advisory fires."""
    values: dict[CasillaId, Decimal] = {_BASE_LIQUIDABLE_GENERAL: Decimal("18000")}
    assert _evaluate_advisory_predicate_fires(_EXPRESSION, values) is True


def test_advisory_does_not_fire_when_cuota_nonzero() -> None:
    """Positive base + non-zero cuota → implication satisfied, no advisory.

    The dominant healthy path: positive taxable base produced a tax liability.
    """
    values: dict[CasillaId, Decimal] = {
        _BASE_LIQUIDABLE_GENERAL: Decimal("18000"),
        _CUOTA_RESULTANTE: Decimal("2480.50"),
    }
    assert _evaluate_advisory_predicate_fires(_EXPRESSION, values) is False


def test_advisory_does_not_fire_when_base_zero() -> None:
    """Zero base liquidable general → implication holds trivially, no advisory.

    A filer with no general taxable base (e.g. savings-only or below the
    declaration floor) must not be flagged.
    """
    values: dict[CasillaId, Decimal] = {
        _BASE_LIQUIDABLE_GENERAL: Decimal("0"),
        _CUOTA_RESULTANTE: Decimal("0"),
    }
    assert _evaluate_advisory_predicate_fires(_EXPRESSION, values) is False


def test_advisory_does_not_fire_when_base_negative() -> None:
    """Negative base → strictly-positive antecedent test holds trivially, no fire.

    A loss / negative general base does not engage the implication.
    """
    values: dict[CasillaId, Decimal] = {
        _BASE_LIQUIDABLE_GENERAL: Decimal("-3000"),
        _CUOTA_RESULTANTE: Decimal("0"),
    }
    assert _evaluate_advisory_predicate_fires(_EXPRESSION, values) is False


# ---------------------------------------------------------------------------
# Finding emission through the shared predicate evaluator
# ---------------------------------------------------------------------------


def test_emits_single_advisory_warning_finding_when_violated() -> None:
    """A violated ADVISORY predicate yields exactly one non-blocking WARNING finding."""
    values: dict[CasillaId, Decimal] = {
        _BASE_LIQUIDABLE_GENERAL: Decimal("18000"),
        _CUOTA_RESULTANTE: Decimal("0"),
    }
    findings = _evaluate_verification_predicates((_predicate(),), values, _profile())
    assert len(findings) == 1
    assert findings[0].kind is ModeloVerificationFindingKind.ADVISORY
    assert findings[0].severity is ModeloVerificationFindingSeverity.WARNING
    assert "ley-35-2006:art-79" in findings[0].legal_refs


def test_emits_no_finding_when_satisfied() -> None:
    """A satisfied ADVISORY predicate (cuota non-zero) yields no finding."""
    values: dict[CasillaId, Decimal] = {
        _BASE_LIQUIDABLE_GENERAL: Decimal("18000"),
        _CUOTA_RESULTANTE: Decimal("2480.50"),
    }
    assert _evaluate_verification_predicates((_predicate(),), values, _profile()) == []


# ---------------------------------------------------------------------------
# Registration on the real M100 2024 + 2025 revisions (read from the snapshot)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("filing_year", [2024, 2025])
def test_settlement_advisory_registered_on_revision(filing_year: int) -> None:
    """The settlement-completeness ADVISORY is wired on the live revision.

    Reads the loaded snapshot — the predicate exists, is ADVISORY, references
    0500 and 0595, and both operands resolve to declared casillas whose
    semantics are base liquidable general (antecedent) and cuota resultante de
    la autoliquidación (consequent). No formula output is asserted.
    """
    snapshot = bundled_authority().snapshot("100", filing_year=filing_year, period="0A")
    matches = [p for p in snapshot.revision.verification_predicates if p.predicate_id.endswith(_PREDICATE_ID_SUFFIX)]
    assert len(matches) == 1, f"expected exactly one settlement guard on M100 {filing_year}"
    predicate = matches[0]
    assert predicate.finding_kind == "ADVISORY"
    assert predicate.expression == _EXPRESSION
    assert "ley-35-2006:art-79" in {str(r) for r in predicate.legal_refs}

    casillas_by_id = {c.id: c for c in snapshot.revision.casillas}
    assert _BASE_LIQUIDABLE_GENERAL in casillas_by_id, "antecedent 0500 must be a declared casilla"
    assert _CUOTA_RESULTANTE in casillas_by_id, "consequent 0595 must be a declared casilla"
    assert casillas_by_id[_BASE_LIQUIDABLE_GENERAL].label.startswith("Base liquidable general")
    assert casillas_by_id[_CUOTA_RESULTANTE].semantic_role == "irpf_cuota_resultante_autoliquidacion"
