"""Modelo 303 régimen simplificado de IVA módulos-engine-vs-declared-C48 advisory predicate.

The estimación-objetiva régimen-simplificado IVA módulos engine keeps
casilla 48 ("RS - 4T -
Suma cuotas derivadas régimen simplificado conjunto actividades") a manual
operator input while wiring a computed reference figure
(``modulos-iva-cuota-derivada``) for a bounded first-slice of tabled IAE
activities. The
``advisory_when_computed_diverges(["48", "modulos-iva-cuota-derivada"])``
predicate surfaces a discrepancy between the two without ever blocking the
filing — the computed reference intentionally omits real cuotas soportadas
por adquisiciones concretas beyond the 1 por ciento forfait, which the
taxpayer may legitimately claim.

Semantics are derived from the ``advisory_when_computed_diverges`` DSL
contract directly (mirroring the M131 estimación-objetiva módulos engine
advisory test), never from any registry formula output — no hand-computed
Decimal, no tautology.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from ....core.resources import resources
from ....domain.calculations.registry import CasillaId, VerificationPredicateDefinition, validated_casilla_id
from ....domain.modelos import ModeloVerificationFindingKind
from .._verification_actions import _evaluate_advisory_predicate_fires, _evaluate_verification_predicates
from ._verification_substance_support import _workflow_profile

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_EXPRESSION = 'advisory_when_computed_diverges(["48", "modulos-iva-cuota-derivada"])'
_CASILLA_48: CasillaId = validated_casilla_id("48", surface="m303 modulos iva advisory test")
_COMPUTED: CasillaId = validated_casilla_id(
    "modulos-iva-cuota-derivada",
    surface="m303 modulos iva advisory test",
)


def _predicate() -> VerificationPredicateDefinition:
    return VerificationPredicateDefinition(
        predicate_id="modelo-303-2023-modulos-iva-computed-diverges-de-c48",
        legal_refs=("ley-37-1992:art-122", "ley-37-1992:art-123", "orden-hac-1347-2024:anexo-i-iva-instrucciones"),
        expression=_EXPRESSION,
        finding_kind="ADVISORY",
    )


def test_advisory_ships_on_the_2023_y_siguientes_revision() -> None:
    """The shipped registry revision carries the computed-diverges predicate."""
    revision = resources().modelos.authority.validate_modelo("303").revisions["2023-y-siguientes"]
    target_predicate_id = "modelo-303-2023-modulos-iva-computed-diverges-de-c48"
    predicate = next(p for p in revision.verification_predicates if p.predicate_id == target_predicate_id)
    assert predicate.finding_kind == "ADVISORY"
    assert predicate.expression == _EXPRESSION
    legal_refs = tuple(str(r) for r in predicate.legal_refs)
    assert "ley-37-1992:art-122" in legal_refs
    assert "ley-37-1992:art-123" in legal_refs


def test_advisory_fires_when_declared_differs_from_computed_by_more_than_a_cent() -> None:
    values: dict[CasillaId, Decimal] = {
        _CASILLA_48: Decimal("5000.00"),
        _COMPUTED: Decimal("6970.49"),
    }
    assert _evaluate_advisory_predicate_fires(_EXPRESSION, values) is True


def test_advisory_fires_when_declared_absent_but_computed_positive() -> None:
    """Absent casilla 48 (reads as Decimal(0)) with a positive computed reference fires."""
    values: dict[CasillaId, Decimal] = {_COMPUTED: Decimal("6970.49")}
    assert _evaluate_advisory_predicate_fires(_EXPRESSION, values) is True


def test_advisory_does_not_fire_when_declared_matches_computed() -> None:
    values: dict[CasillaId, Decimal] = {
        _CASILLA_48: Decimal("6970.49"),
        _COMPUTED: Decimal("6970.49"),
    }
    assert _evaluate_advisory_predicate_fires(_EXPRESSION, values) is False


def test_advisory_does_not_fire_within_one_cent_tolerance() -> None:
    values: dict[CasillaId, Decimal] = {
        _CASILLA_48: Decimal("6970.48"),
        _COMPUTED: Decimal("6970.49"),
    }
    assert _evaluate_advisory_predicate_fires(_EXPRESSION, values) is False


def test_advisory_does_not_fire_when_computed_is_zero_untabled_activity() -> None:
    """Zero computed reference (untabled epígrafe) → nothing to reconcile against, no fire.

    A filer whose activity is not yet in the bounded first-slice coefficient
    table has no engine coverage; casilla 48 stays the sole authoritative
    manual input and no discrepancy prompt is meaningful.
    """
    values: dict[CasillaId, Decimal] = {
        _CASILLA_48: Decimal("2500.00"),
        _COMPUTED: Decimal("0"),
    }
    assert _evaluate_advisory_predicate_fires(_EXPRESSION, values) is False


def test_advisory_does_not_fire_when_computed_absent() -> None:
    values: dict[CasillaId, Decimal] = {_CASILLA_48: Decimal("2500.00")}
    assert _evaluate_advisory_predicate_fires(_EXPRESSION, values) is False


def test_emits_single_advisory_warning_finding_when_violated() -> None:
    values: dict[CasillaId, Decimal] = {
        _CASILLA_48: Decimal("5000.00"),
        _COMPUTED: Decimal("6970.49"),
    }
    findings = _evaluate_verification_predicates((_predicate(),), values, _workflow_profile())
    assert len(findings) == 1
    assert findings[0].kind is ModeloVerificationFindingKind.ADVISORY
