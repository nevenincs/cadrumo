"""M151 (régimen impatriados) silent-under-declaration verification advisory tests."""

from __future__ import annotations

from decimal import Decimal

import pytest

from ....core import CasillaId, validated_casilla_id
from ....core.resources import bundled_path
from ....domain.calculations.registry.authority import bundled_authority
from ....domain.calculations.registry.loader import load_registry_tree
from ....domain.calculations.registry.schema_verification import VerificationPredicateDefinition
from ....domain.modelos import (
    ModeloVerificationFindingKind,
    ModeloVerificationFindingSeverity,
)
from .._verification_actions import evaluate_verification_predicates
from ._verification_substance_support import _workflow_profile

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_M151_ADVISORY_PREDICATE_ID = "modelo-151-base-liquidable-implica-cuota-integra"
_M151_BASE_LIQUIDABLE: CasillaId = validated_casilla_id(
    "impatriado.base-liquidable-general",
    surface="test_verification_m151_advisory._M151_BASE_LIQUIDABLE",
)
_M151_CUOTA_INTEGRA: CasillaId = validated_casilla_id(
    "impatriado.cuota-integra-general",
    surface="test_verification_m151_advisory._M151_CUOTA_INTEGRA",
)


def _m151_advisory_predicate() -> VerificationPredicateDefinition:
    """Load the shipped M151 silent-under-declaration advisory from the authority."""
    # Resolved by (modelo, filing_year, period) rather than by a literal id.
    # The subscript this replaces named `2015-y-siguientes`, which the registry
    # stopped shipping when that window was split into `2015-2022` and
    # `2025-y-siguientes` -- the test then died on a KeyError before reaching
    # anything it asserts. Letting the law pick the revision keeps it pointed at
    # whichever window governs the latest supported filing year, so the next
    # split moves it automatically. (The successor's name understates its
    # reach: it opens on 2023-01-01.)
    authority = bundled_authority()
    _modelos, catalogues = load_registry_tree(bundled_path("registry", "aeat"))
    declared_years = catalogues.supported_filing_years
    assert declared_years is not None, "the bundled registry declares no supported filing years"
    revision = authority.snapshot(
        "151",
        filing_year=max(declared_years.years),
        period="0A",
    ).revision
    predicate = next(
        (p for p in revision.verification_predicates if p.predicate_id == _M151_ADVISORY_PREDICATE_ID),
        None,
    )
    assert predicate is not None, (
        f"revision {revision.id} ships no predicate {_M151_ADVISORY_PREDICATE_ID!r}; it declares "
        f"{sorted(p.predicate_id for p in revision.verification_predicates)}"
    )
    assert predicate.finding_kind == "ADVISORY"
    assert predicate.expression == (
        'implies_nonzero(["impatriado.base-liquidable-general", "impatriado.cuota-integra-general"])'
    )
    return predicate


def test_m151_advisory_ships_in_2015_revision() -> None:
    """The 2015-y-siguientes revision carries the base-liquidable->cuota-integra advisory."""
    predicate = _m151_advisory_predicate()
    assert "ley-35-2006:art-93" in tuple(str(r) for r in predicate.legal_refs)


def test_m151_advisory_fires_when_base_liquidable_positive_but_cuota_zero() -> None:
    """Positive base liquidable with zero cuota integra surfaces a warning advisory."""
    predicate = _m151_advisory_predicate()
    casilla_values: dict[CasillaId, Decimal] = {
        _M151_BASE_LIQUIDABLE: Decimal("85000.00"),
        _M151_CUOTA_INTEGRA: Decimal("0"),
    }

    findings = evaluate_verification_predicates((predicate,), casilla_values, _workflow_profile())

    assert len(findings) == 1
    assert findings[0].kind is ModeloVerificationFindingKind.ADVISORY
    assert findings[0].severity is ModeloVerificationFindingSeverity.WARNING
    assert "ley-35-2006:art-93" in findings[0].legal_refs


def test_m151_advisory_silent_when_cuota_integra_present() -> None:
    """Positive base liquidable and positive cuota integra satisfy the implication."""
    predicate = _m151_advisory_predicate()
    casilla_values: dict[CasillaId, Decimal] = {
        _M151_BASE_LIQUIDABLE: Decimal("85000.00"),
        _M151_CUOTA_INTEGRA: Decimal("20400.00"),
    }

    findings = evaluate_verification_predicates((predicate,), casilla_values, _workflow_profile())
    assert findings == []


def test_m151_advisory_silent_when_base_liquidable_zero_or_negative() -> None:
    """No (or negative) base liquidable general holds trivially."""
    predicate = _m151_advisory_predicate()

    explicit_zero: dict[CasillaId, Decimal] = {
        _M151_BASE_LIQUIDABLE: Decimal("0"),
        _M151_CUOTA_INTEGRA: Decimal("0"),
    }
    negative: dict[CasillaId, Decimal] = {
        _M151_BASE_LIQUIDABLE: Decimal("-100.00"),
        _M151_CUOTA_INTEGRA: Decimal("0"),
    }
    absent: dict[CasillaId, Decimal] = {}

    assert evaluate_verification_predicates((predicate,), explicit_zero, _workflow_profile()) == []
    assert evaluate_verification_predicates((predicate,), negative, _workflow_profile()) == []
    assert evaluate_verification_predicates((predicate,), absent, _workflow_profile()) == []
