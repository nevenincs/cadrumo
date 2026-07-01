"""Modelo 100 anualidades-por-alimentos cuota-review advisory tests.

Covers the ``modelo-100-YYYY-anualidades-alimentos-hijos-revisar-cuota-escala-separada``
ADVISORY guard shipped on the 2024 and 2025 revisions. Anualidades por alimentos
a favor de los hijos satisfechas por decisión judicial (casilla 0527) receive a
separate-escala treatment under LIRPF art. 64 (state scale) and art. 75
(autonomic scale): the escala progresiva is applied separately to the
anualidades and to the rest of the base liquidable general, and the statutory
régimen raises the mínimo personal y familiar by 1.980 €. The current M100 cuota
chain applies neither adjustment, so a payer declaring anualidades is
under-taxed. The interim non-blocking ADVISORY (issue #532 tracks the full
separate-escala modelling) fires whenever anualidades are declared (0527 > 0),
prompting an operator cuota review, per no-silent-under-declaration.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from ....core.resources import resources
from ....domain.calculations.registry._ids import CasillaId, validated_casilla_id
from ....domain.calculations.registry._schema import VerificationPredicateDefinition
from ....domain.modelos._verification_report import (
    ModeloVerificationFindingKind,
    ModeloVerificationFindingSeverity,
)
from .._verification_actions import evaluate_verification_predicates
from ._verification_substance_support import _workflow_profile

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_ANUALIDADES_TOTAL: CasillaId = validated_casilla_id(
    "0527",
    surface="test_verification_m100_anualidades_advisory",
)


def _predicate_id(year: str) -> str:
    return f"modelo-100-{year}-anualidades-alimentos-hijos-revisar-cuota-escala-separada"


def _anualidades_advisory_predicate(year: str) -> VerificationPredicateDefinition:
    """Load the shipped M100 anualidades cuota-review advisory for a revision year."""
    revision = resources().modelos.authority.validate_modelo("100").revisions[year]
    predicate = next(p for p in revision.verification_predicates if p.predicate_id == _predicate_id(year))
    assert predicate.finding_kind == "ADVISORY"
    assert predicate.expression == 'advisory_when_positive(["0527"])'
    return predicate


@pytest.mark.parametrize("year", ["2024", "2025"])
def test_anualidades_advisory_ships_with_art_64_and_75_grounding(year: str) -> None:
    """The advisory cites LIRPF art. 64 (state escala) and art. 75 (autonomic escala)."""
    predicate = _anualidades_advisory_predicate(year)
    legal_refs = tuple(str(r) for r in predicate.legal_refs)
    assert "ley-35-2006:art-64" in legal_refs
    assert "ley-35-2006:art-75" in legal_refs


@pytest.mark.parametrize("year", ["2024", "2025"])
def test_anualidades_advisory_fires_when_declared(year: str) -> None:
    """A positive anualidades total (0527 > 0) surfaces a warning advisory."""
    predicate = _anualidades_advisory_predicate(year)
    casilla_values: dict[CasillaId, Decimal] = {_ANUALIDADES_TOTAL: Decimal("4800.00")}

    findings = evaluate_verification_predicates((predicate,), casilla_values, _workflow_profile())

    assert len(findings) == 1
    assert findings[0].kind is ModeloVerificationFindingKind.ADVISORY
    assert findings[0].severity is ModeloVerificationFindingSeverity.WARNING
    assert "ley-35-2006:art-64" in findings[0].legal_refs
    assert "ley-35-2006:art-75" in findings[0].legal_refs
    assert findings[0].message  # a non-empty operator-facing message is rendered


@pytest.mark.parametrize("year", ["2024", "2025"])
def test_anualidades_advisory_fires_on_smallest_positive_amount(year: str) -> None:
    """The trigger is strict positivity — a one-cent anualidades total fires."""
    predicate = _anualidades_advisory_predicate(year)
    casilla_values: dict[CasillaId, Decimal] = {_ANUALIDADES_TOTAL: Decimal("0.01")}

    findings = evaluate_verification_predicates((predicate,), casilla_values, _workflow_profile())
    assert len(findings) == 1


@pytest.mark.parametrize("year", ["2024", "2025"])
def test_anualidades_advisory_silent_when_not_declared(year: str) -> None:
    """A zero or absent anualidades total holds the check trivially — no advisory."""
    predicate = _anualidades_advisory_predicate(year)

    explicit_zero: dict[CasillaId, Decimal] = {_ANUALIDADES_TOTAL: Decimal("0")}
    absent: dict[CasillaId, Decimal] = {}

    assert evaluate_verification_predicates((predicate,), explicit_zero, _workflow_profile()) == []
    assert evaluate_verification_predicates((predicate,), absent, _workflow_profile()) == []


@pytest.mark.parametrize("year", ["2024", "2025"])
def test_anualidades_advisory_silent_for_negative_value(year: str) -> None:
    """A negative value does not satisfy strict positivity — no advisory."""
    predicate = _anualidades_advisory_predicate(year)
    casilla_values: dict[CasillaId, Decimal] = {_ANUALIDADES_TOTAL: Decimal("-100.00")}

    assert evaluate_verification_predicates((predicate,), casilla_values, _workflow_profile()) == []
