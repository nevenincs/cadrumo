"""M131 silent-under-declaration verification advisory tests."""

from __future__ import annotations

from decimal import Decimal
from functools import lru_cache

import pytest

from ....core.casilla_id import CasillaId
from ....domain.calculations.registry.authority import bundled_authority
from ....domain.calculations.registry.schema_verification import VerificationPredicateDefinition
from ....domain.modelos.verification_report import ModeloVerificationFindingKind, ModeloVerificationFindingSeverity
from ..verification_actions import evaluate_verification_predicates
from ._verification_substance_support import _CASILLA_01, _CASILLA_02, _workflow_profile

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_M131_ADVISORY_PREDICATE_IDS = {
    "2019-2023": "modelo-131-2019-2023-pago-fraccionado-determinado-cuando-rendimientos-positivos",
    "2024": "modelo-131-2024-pago-fraccionado-determinado-cuando-rendimientos-positivos",
    "2025": "modelo-131-2025-pago-fraccionado-determinado-cuando-rendimientos-positivos",
    "2026": "modelo-131-2026-pago-fraccionado-determinado-cuando-rendimientos-positivos",
}
_M131_REVISION_IDS = tuple(sorted(_M131_ADVISORY_PREDICATE_IDS))


@lru_cache
def _m131_advisory_predicate(revision_id: str) -> VerificationPredicateDefinition:
    """Load the shipped M131 silent-under-declaration advisory from the authority."""
    revision = bundled_authority().validate_modelo("131").revisions[revision_id]
    predicate_id = _M131_ADVISORY_PREDICATE_IDS[revision_id]
    predicate = next(p for p in revision.verification_predicates if p.predicate_id == predicate_id)
    assert predicate.finding_kind == "ADVISORY"
    assert predicate.expression == 'implies_nonzero(["01", "02"])'
    return predicate


def test_m131_advisory_ships_in_every_revision() -> None:
    """Every M131 revision carries the C01->C02 silent-under-declaration advisory."""
    for revision_id in _M131_REVISION_IDS:
        predicate = _m131_advisory_predicate(revision_id)
        assert "rd-439-2007:art-110" in tuple(str(r) for r in predicate.legal_refs), revision_id


def test_m131_advisory_fires_when_rendimientos_positive_but_pago_zero() -> None:
    """Positive C01 with zero C02 surfaces a warning advisory."""
    for revision_id in _M131_REVISION_IDS:
        predicate = _m131_advisory_predicate(revision_id)
        casilla_values: dict[CasillaId, Decimal] = {
            _CASILLA_01: Decimal("18000.00"),
            _CASILLA_02: Decimal("0"),
        }

        findings = evaluate_verification_predicates((predicate,), casilla_values, _workflow_profile())

        assert len(findings) == 1, revision_id
        assert findings[0].kind is ModeloVerificationFindingKind.ADVISORY, revision_id
        assert findings[0].severity is ModeloVerificationFindingSeverity.WARNING, revision_id
        assert "rd-439-2007:art-110" in findings[0].legal_refs, revision_id


def test_m131_advisory_silent_when_pago_fraccionado_present() -> None:
    """Positive C01 and positive C02 satisfy the implication."""
    for revision_id in _M131_REVISION_IDS:
        predicate = _m131_advisory_predicate(revision_id)
        casilla_values: dict[CasillaId, Decimal] = {
            _CASILLA_01: Decimal("18000.00"),
            _CASILLA_02: Decimal("360.00"),
        }

        findings = evaluate_verification_predicates((predicate,), casilla_values, _workflow_profile())
        assert findings == [], revision_id


def test_m131_advisory_silent_when_no_datos_base_activity() -> None:
    """No datos-base rendimientos holds trivially."""
    for revision_id in _M131_REVISION_IDS:
        predicate = _m131_advisory_predicate(revision_id)

        explicit_zero: dict[CasillaId, Decimal] = {_CASILLA_01: Decimal("0"), _CASILLA_02: Decimal("0")}
        absent: dict[CasillaId, Decimal] = {}

        assert evaluate_verification_predicates((predicate,), explicit_zero, _workflow_profile()) == [], revision_id
        assert evaluate_verification_predicates((predicate,), absent, _workflow_profile()) == [], revision_id
