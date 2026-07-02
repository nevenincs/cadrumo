"""M210 IRNR silent-under-declaration verification advisory tests.

Covers the ``modelo-210-2025-rendimientos-integros-implica-base-imponible``
ADVISORY guard appended alongside the pre-existing
``m210-representante-fiscal-required`` BLOCKING_RULE predicate (left
untouched). The general / UE-EEE branch's ``base_imponible`` is computed
from ``rendimientos_integros`` via the ``m210-base-imponible-2025`` formula;
a positive ``rendimientos_integros`` with a zero ``base_imponible`` is
unexpected on that branch and must surface a non-blocking advisory rather
than silently granting ``VERIFICADO_COMPLETO``, per no-silent-under-declaration.

Also covers the ``modelo-210-2025-inmobiliaria-implica-base-imponible``
ADVISORY guard (the m210 categorical-conditional predicate decision): the
inmobiliaria branch's silent-zero risk is gated on a categorical equality
(``tipo_renta == "inmobiliaria"``), evaluated against the operator-entered
raw text value rather than the Decimal casilla_values projection.
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

_PREDICATE_ID = "modelo-210-2025-rendimientos-integros-implica-base-imponible"
_INMOBILIARIA_PREDICATE_ID = "modelo-210-2025-inmobiliaria-implica-base-imponible"
_RENDIMIENTOS_INTEGROS: CasillaId = validated_casilla_id(
    "rendimientos_integros",
    surface="test_verification_m210_advisory",
)
_BASE_IMPONIBLE: CasillaId = validated_casilla_id(
    "base_imponible",
    surface="test_verification_m210_advisory",
)
_TIPO_RENTA: CasillaId = validated_casilla_id(
    "tipo_renta",
    surface="test_verification_m210_advisory",
)


def _m210_advisory_predicate() -> VerificationPredicateDefinition:
    """Load the shipped M210 base-imponible silent-under-declaration advisory."""
    revision = resources().modelos.authority.validate_modelo("210").revisions["2025"]
    predicate = next(p for p in revision.verification_predicates if p.predicate_id == _PREDICATE_ID)
    assert predicate.finding_kind == "ADVISORY"
    assert predicate.expression == 'implies_nonzero(["rendimientos_integros", "base_imponible"])'
    return predicate


def test_m210_representante_fiscal_predicate_is_preserved_alongside_advisory() -> None:
    """The pre-existing BLOCKING_RULE representante-fiscal predicate stays untouched."""
    revision = resources().modelos.authority.validate_modelo("210").revisions["2025"]
    representante_fiscal = next(
        p for p in revision.verification_predicates if p.predicate_id == "m210-representante-fiscal-required"
    )
    assert representante_fiscal.finding_kind == "BLOCKING_RULE"
    assert representante_fiscal.expression == (
        'profile_field_required("representante_fiscal_nif", "non_resident_irnr_non_eea")'
    )
    assert "trlirnr-rdleg-5-2004:art-10" in tuple(str(r) for r in representante_fiscal.legal_refs)


def test_m210_advisory_ships_with_art_24_grounding() -> None:
    """The new advisory cites TRLIRNR art. 24 (base imponible determination)."""
    predicate = _m210_advisory_predicate()
    assert "trlirnr-rdleg-5-2004:art-24" in tuple(str(r) for r in predicate.legal_refs)


def test_m210_advisory_fires_when_rendimientos_positive_but_base_zero() -> None:
    """Positive rendimientos_integros with zero base_imponible surfaces a warning advisory."""
    predicate = _m210_advisory_predicate()
    casilla_values: dict[CasillaId, Decimal] = {
        _RENDIMIENTOS_INTEGROS: Decimal("5000.00"),
        _BASE_IMPONIBLE: Decimal("0"),
    }

    findings = evaluate_verification_predicates((predicate,), casilla_values, _workflow_profile())

    assert len(findings) == 1
    assert findings[0].kind is ModeloVerificationFindingKind.ADVISORY
    assert findings[0].severity is ModeloVerificationFindingSeverity.WARNING
    assert "trlirnr-rdleg-5-2004:art-24" in findings[0].legal_refs


def test_m210_advisory_silent_when_base_imponible_present() -> None:
    """Positive rendimientos_integros and positive base_imponible satisfy the implication."""
    predicate = _m210_advisory_predicate()
    casilla_values: dict[CasillaId, Decimal] = {
        _RENDIMIENTOS_INTEGROS: Decimal("5000.00"),
        _BASE_IMPONIBLE: Decimal("4500.00"),
    }

    findings = evaluate_verification_predicates((predicate,), casilla_values, _workflow_profile())
    assert findings == []


def test_m210_advisory_silent_when_no_rendimientos() -> None:
    """Zero or negative rendimientos_integros holds the implication trivially."""
    predicate = _m210_advisory_predicate()

    explicit_zero: dict[CasillaId, Decimal] = {
        _RENDIMIENTOS_INTEGROS: Decimal("0"),
        _BASE_IMPONIBLE: Decimal("0"),
    }
    negative: dict[CasillaId, Decimal] = {
        _RENDIMIENTOS_INTEGROS: Decimal("-100.00"),
        _BASE_IMPONIBLE: Decimal("0"),
    }
    absent: dict[CasillaId, Decimal] = {}

    assert evaluate_verification_predicates((predicate,), explicit_zero, _workflow_profile()) == []
    assert evaluate_verification_predicates((predicate,), negative, _workflow_profile()) == []
    assert evaluate_verification_predicates((predicate,), absent, _workflow_profile()) == []


def _m210_inmobiliaria_advisory_predicate() -> VerificationPredicateDefinition:
    """Load the shipped M210 inmobiliaria-branch categorical-conditional advisory."""
    revision = resources().modelos.authority.validate_modelo("210").revisions["2025"]
    predicate = next(p for p in revision.verification_predicates if p.predicate_id == _INMOBILIARIA_PREDICATE_ID)
    assert predicate.finding_kind == "ADVISORY"
    assert predicate.expression == ('casilla_equals_implies_nonzero(["tipo_renta", "inmobiliaria", "base_imponible"])')
    return predicate


def test_m210_inmobiliaria_advisory_ships_with_art_13_1_h_grounding() -> None:
    """The inmobiliaria advisory cites TRLIRNR art. 13.1.h (imputed Spanish-source income)."""
    predicate = _m210_inmobiliaria_advisory_predicate()
    legal_refs = tuple(str(r) for r in predicate.legal_refs)
    assert "trlirnr-rdleg-5-2004:art-13.1.h" in legal_refs
    assert "trlirnr-rdleg-5-2004:art-24" in legal_refs


def test_m210_inmobiliaria_advisory_fires_when_tipo_renta_inmobiliaria_and_base_zero() -> None:
    """tipo_renta == "inmobiliaria" with a zero base_imponible surfaces a warning advisory."""
    predicate = _m210_inmobiliaria_advisory_predicate()
    casilla_values: dict[CasillaId, Decimal] = {_BASE_IMPONIBLE: Decimal("0")}
    text_values: dict[CasillaId, str] = {_TIPO_RENTA: "inmobiliaria"}

    findings = evaluate_verification_predicates((predicate,), casilla_values, _workflow_profile(), text_values)

    assert len(findings) == 1
    assert findings[0].kind is ModeloVerificationFindingKind.ADVISORY
    assert findings[0].severity is ModeloVerificationFindingSeverity.WARNING
    assert "trlirnr-rdleg-5-2004:art-13.1.h" in findings[0].legal_refs


def test_m210_inmobiliaria_advisory_silent_when_base_imponible_present() -> None:
    """tipo_renta == "inmobiliaria" with a positive base_imponible satisfies the implication."""
    predicate = _m210_inmobiliaria_advisory_predicate()
    casilla_values: dict[CasillaId, Decimal] = {_BASE_IMPONIBLE: Decimal("2200.50")}
    text_values: dict[CasillaId, str] = {_TIPO_RENTA: "inmobiliaria"}

    findings = evaluate_verification_predicates((predicate,), casilla_values, _workflow_profile(), text_values)
    assert findings == []


def test_m210_inmobiliaria_advisory_silent_when_tipo_renta_is_not_inmobiliaria() -> None:
    """A non-inmobiliaria tipo_renta holds the implication trivially regardless of base_imponible."""
    predicate = _m210_inmobiliaria_advisory_predicate()

    general_zero_base: dict[CasillaId, Decimal] = {_BASE_IMPONIBLE: Decimal("0")}
    general_text: dict[CasillaId, str] = {_TIPO_RENTA: "general"}
    no_text_values: dict[CasillaId, Decimal] = {_BASE_IMPONIBLE: Decimal("0")}

    assert evaluate_verification_predicates((predicate,), general_zero_base, _workflow_profile(), general_text) == []
    # No text_values at all (tipo_renta unresolved) also holds trivially.
    assert evaluate_verification_predicates((predicate,), no_text_values, _workflow_profile()) == []
