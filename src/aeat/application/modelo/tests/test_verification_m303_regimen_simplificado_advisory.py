"""M303 régimen simplificado silent-under-declaration verification advisory tests.

The first slice (Option C) of the
modulos-based IVA cuota engine: casillas 47-58 (the régimen simplificado
apartado, LIVA arts. 122-124) are all authored ``input_kind = "manual"`` with
no binding or formula, so an estimación-objetiva filer who declares the 1T-3T
"ingresos a cuenta" (casilla 47) but leaves the 4T "cuota derivada del régimen
simplificado" (casilla 48) at zero would file a zero-cuota result with no
gate. This module pins the ``implies_nonzero(["47", "48"])`` ADVISORY guard
shipped on both M303 revisions (2009-y-siguientes inline, 2023-y-siguientes
fragmented — registry-revision-content-inline-or-fragmented).
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from ....core.resources import resources
from ....domain.calculations.registry import (
    CasillaId,
    VerificationPredicateDefinition,
    validated_casilla_id,
)
from ....domain.modelos import (
    ModeloVerificationFindingKind,
    ModeloVerificationFindingSeverity,
)
from .._verification_actions import evaluate_verification_predicates
from ._verification_substance_support import _workflow_profile

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_M303_ADVISORY_PREDICATE_IDS = {
    "2009-y-siguientes": "modelo-303-2009-regimen-simplificado-cuota-determinada-cuando-ingresos",
    "2023-y-siguientes": "modelo-303-regimen-simplificado-cuota-determinada-cuando-ingresos-declarados",
}

_CASILLA_47: CasillaId = validated_casilla_id("47", surface="test casilla id")
_CASILLA_48: CasillaId = validated_casilla_id("48", surface="test casilla id")


def _m303_advisory_predicate(revision_id: str) -> VerificationPredicateDefinition:
    """Load the shipped M303 régimen simplificado silent-under-declaration advisory."""
    revision = resources().modelos.authority.validate_modelo("303").revisions[revision_id]
    predicate_id = _M303_ADVISORY_PREDICATE_IDS[revision_id]
    predicate = next(p for p in revision.verification_predicates if p.predicate_id == predicate_id)
    assert predicate.finding_kind == "ADVISORY"
    assert predicate.expression == 'implies_nonzero(["47", "48"])'
    return predicate


@pytest.mark.parametrize("revision_id", sorted(_M303_ADVISORY_PREDICATE_IDS))
def test_m303_regimen_simplificado_advisory_ships_in_every_revision(revision_id: str) -> None:
    """Every M303 revision carries the C47->C48 silent-under-declaration advisory."""
    predicate = _m303_advisory_predicate(revision_id)
    legal_refs = tuple(str(r) for r in predicate.legal_refs)
    assert "ley-37-1992:art-122" in legal_refs
    assert "ley-37-1992:art-123" in legal_refs


@pytest.mark.parametrize("revision_id", sorted(_M303_ADVISORY_PREDICATE_IDS))
def test_m303_regimen_simplificado_advisory_fires_when_ingresos_positive_but_cuota_zero(revision_id: str) -> None:
    """Positive C47 (ingresos a cuenta) with zero C48 (cuota derivada) surfaces a warning advisory."""
    predicate = _m303_advisory_predicate(revision_id)
    casilla_values: dict[CasillaId, Decimal] = {
        _CASILLA_47: Decimal("1250.00"),
        _CASILLA_48: Decimal("0"),
    }

    findings = evaluate_verification_predicates((predicate,), casilla_values, _workflow_profile())

    assert len(findings) == 1
    assert findings[0].kind is ModeloVerificationFindingKind.ADVISORY
    assert findings[0].severity is ModeloVerificationFindingSeverity.WARNING
    assert "ley-37-1992:art-122" in findings[0].legal_refs
    assert "ley-37-1992:art-123" in findings[0].legal_refs


@pytest.mark.parametrize("revision_id", sorted(_M303_ADVISORY_PREDICATE_IDS))
def test_m303_regimen_simplificado_advisory_silent_when_cuota_present(revision_id: str) -> None:
    """Positive C47 and positive C48 (4T settlement completed) satisfy the implication."""
    predicate = _m303_advisory_predicate(revision_id)
    casilla_values: dict[CasillaId, Decimal] = {
        _CASILLA_47: Decimal("1250.00"),
        _CASILLA_48: Decimal("1980.45"),
    }

    findings = evaluate_verification_predicates((predicate,), casilla_values, _workflow_profile())
    assert findings == []


@pytest.mark.parametrize("revision_id", sorted(_M303_ADVISORY_PREDICATE_IDS))
def test_m303_regimen_simplificado_advisory_silent_for_regimen_general_filer(revision_id: str) -> None:
    """A régimen-general filer (no simplificado activity, both casillas zero/absent) holds trivially."""
    predicate = _m303_advisory_predicate(revision_id)

    explicit_zero: dict[CasillaId, Decimal] = {_CASILLA_47: Decimal("0"), _CASILLA_48: Decimal("0")}
    absent: dict[CasillaId, Decimal] = {}

    assert evaluate_verification_predicates((predicate,), explicit_zero, _workflow_profile()) == []
    assert evaluate_verification_predicates((predicate,), absent, _workflow_profile()) == []
