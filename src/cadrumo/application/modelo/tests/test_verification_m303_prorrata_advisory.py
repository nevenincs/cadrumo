"""M303 prorrata settlement silent-under-declaration verification advisory tests.

Casilla 44 (regularización de prorrata por porcentaje definitivo, LIVA art.
105.Cuatro) is authored ``input_kind = "manual"`` with no formula on every M303
revision, because the amount needs the provisional percentage of art. 105.Uno
(the prior ejercicio's definitive, carried in the profile-scoped prorrata
register) and the art. 105.Seis sum of the year's cuotas soportadas across the
regularised quarters — neither of which is a casilla of the revision, so
neither is expressible as a single-period registry formula. The value is
supplied by the ``prorrata_regularizacion`` binding and its enrolled resolver
instead. What guards the remaining silent-under-declaration shape — a declared
annual prorrata volume with casilla 44 left blank — is the
``implies_nonzero(["iva.prorrata-volumen-total", "44"])`` ADVISORY predicate,
and this module pins it on EVERY shipped revision.

Covering every revision rather than the newest one is the point: the guard
shipped on the 2023 revision alone for a period, so an amended filing for any
year from 2009 to 2022 declaring annual prorrata volumes with a blank casilla
44 passed verify with zero findings. The revisions are discovered from the
registry and each is additionally reached through the law-determined resolver
for a filing year inside its own window, so a fourth revision, or a shifted
window, cannot silently reintroduce an unguarded settlement box.

See Also:
    :class:`~domain.calculations.registry.VerificationPredicateDefinition`
        Registry-authored predicate type loaded from the M303 revisions.
    :func:`~application.modelo._verification_actions.evaluate_verification_predicates`
        Verification predicate evaluator exercised directly by these tests.
    :class:`~ModeloVerificationFindingKind`
        Finding-kind enum proving the guard remains advisory, not blocking.
    :func:`~application.modelo.tests._verification_substance_support._workflow_profile`
        Real workflow-profile fixture used by the predicate evaluator.
    :mod:`~application.modelo.tests.test_prorrata_regularizacion_advisory`
        Calculate-path prorrata advisory regression that complements this
        settlement verify gate.
"""

from __future__ import annotations

from decimal import Decimal
from functools import lru_cache

import pytest

from ....core.casilla_id import CasillaId, validated_casilla_id
from ....domain.calculations.registry.authority import bundled_authority
from ....domain.calculations.registry.schema import ModeloRevision
from ....domain.calculations.registry.schema_verification import VerificationPredicateDefinition
from ....domain.modelos.verification_report import ModeloVerificationFindingKind, ModeloVerificationFindingSeverity
from .._verification_actions import evaluate_verification_predicates
from ._verification_substance_support import _workflow_profile

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_EXPRESSION = 'implies_nonzero(["iva.prorrata-volumen-total", "44"])'
_PRORRATA_BINDING_SOURCE = "prorrata_regularizacion"

_VOLUMEN_TOTAL: CasillaId = validated_casilla_id("iva.prorrata-volumen-total", surface="test casilla id")
_CASILLA_44: CasillaId = validated_casilla_id("44", surface="test casilla id")

#: One filing year inside each shipped revision's serving window, used to reach
#: the revision through the law-determined resolver rather than by literal id.
_PROBE_FILING_YEARS: tuple[int, ...] = (2020, 2024)


@lru_cache
def _m303_revisions() -> tuple[tuple[str, ModeloRevision], ...]:
    """Every shipped M303 revision, discovered from the registry rather than listed."""
    modelo = bundled_authority().validate_modelo("303")
    return tuple(sorted(modelo.revisions.items()))


def _prorrata_predicates(revision: ModeloRevision) -> tuple[VerificationPredicateDefinition, ...]:
    return tuple(predicate for predicate in revision.verification_predicates if predicate.expression == _EXPRESSION)


def _sole_prorrata_predicate(revision_id: str, revision: ModeloRevision) -> VerificationPredicateDefinition:
    predicates = _prorrata_predicates(revision)
    assert len(predicates) == 1, f"{revision_id}: expected exactly one casilla-44 settlement advisory"
    return predicates[0]


def test_every_m303_revision_ships_the_casilla_44_settlement_advisory() -> None:
    """Every shipped M303 revision carries the ADVISORY guard with its art. 104/105 grounding."""
    revisions = _m303_revisions()
    assert len(revisions) >= 2, "M303 must ship more than one revision for this parity check to mean anything"

    for revision_id, revision in revisions:
        predicate = _sole_prorrata_predicate(revision_id, revision)
        assert predicate.finding_kind == "ADVISORY", revision_id
        legal_refs = tuple(str(ref) for ref in predicate.legal_refs)
        assert "ley-37-1992:art-104" in legal_refs, revision_id
        assert "ley-37-1992:art-105" in legal_refs, revision_id


def test_the_revision_serving_each_probe_filing_year_carries_the_advisory() -> None:
    """The law-determined revision for a year in each window carries the guard.

    Reaching the revision through the resolver rather than by literal id is what
    the revision-id-keyed version of this check could not do: it is the filing
    year an operator actually files that must land on a guarded revision.
    """
    reached: set[str] = set()
    for filing_year in _PROBE_FILING_YEARS:
        snapshot = bundled_authority().snapshot("303", filing_year=filing_year, period="4T")
        revision = snapshot.revision
        reached.add(revision.id)
        assert _prorrata_predicates(revision), f"{filing_year} resolves to unguarded revision {revision.id}"

    assert len(reached) == len(_PROBE_FILING_YEARS), (
        "the probe years must reach distinct revisions or this check covers only one of them"
    )


def test_casilla_44_stays_binding_fed_rather_than_formula_fed_on_every_revision() -> None:
    """Casilla 44 declares no formula, and the binding that supplies it is present.

    This pins the mechanism decision recorded at the casilla declaration: the
    art. 105.Cuatro amount is produced by the ``prorrata_regularizacion``
    binding and its enrolled resolver, not by a registry formula. A revision may
    not leave casilla 44 formula-less AND drop the binding that feeds it, which
    would return the box to unaided operator entry.

    Stated honestly, this is a legibility pin rather than the last line of
    defence: registry validation already refuses both halves independently — a
    casilla referencing a formula that targets a different casilla fails
    reference validation, and the binding is a member of a declared construct so
    deleting it fails the same check. Neither half can therefore be
    mutation-flipped in isolation, and this test's value is that a reader of the
    verification surface finds the mechanism decision asserted where the guard
    for it lives.
    """
    for revision_id, revision in _m303_revisions():
        casilla_44 = next(casilla for casilla in revision.casillas if casilla.id == _CASILLA_44)
        assert casilla_44.formula is None, revision_id
        binding_ids = tuple(
            binding.id for binding in revision.bindings if binding.source.value == _PRORRATA_BINDING_SOURCE
        )
        assert binding_ids, f"{revision_id}: casilla 44 has no formula and no prorrata_regularizacion binding"


def test_advisory_fires_when_volume_declared_but_casilla_44_zero() -> None:
    """Declared annual prorrata volume with zero C44 surfaces a non-blocking warning."""
    casilla_values: dict[CasillaId, Decimal] = {
        _VOLUMEN_TOTAL: Decimal("100000.00"),
        _CASILLA_44: Decimal("0"),
    }

    for revision_id, revision in _m303_revisions():
        predicate = _sole_prorrata_predicate(revision_id, revision)

        findings = evaluate_verification_predicates((predicate,), casilla_values, _workflow_profile())

        assert len(findings) == 1, revision_id
        assert findings[0].kind is ModeloVerificationFindingKind.ADVISORY, revision_id
        assert findings[0].severity is ModeloVerificationFindingSeverity.WARNING, revision_id
        assert "ley-37-1992:art-104" in findings[0].legal_refs, revision_id
        assert "ley-37-1992:art-105" in findings[0].legal_refs, revision_id


def test_advisory_silent_when_casilla_44_present() -> None:
    """A non-zero settlement regularizacion satisfies the implication."""
    casilla_values: dict[CasillaId, Decimal] = {
        _VOLUMEN_TOTAL: Decimal("100000.00"),
        _CASILLA_44: Decimal("-217.60"),
    }

    for revision_id, revision in _m303_revisions():
        predicate = _sole_prorrata_predicate(revision_id, revision)
        assert evaluate_verification_predicates((predicate,), casilla_values, _workflow_profile()) == [], revision_id


def test_advisory_silent_for_art94_full_deduction_default() -> None:
    """No annual prorrata volume data keeps the full-deduction default untouched."""
    explicit_zero: dict[CasillaId, Decimal] = {_VOLUMEN_TOTAL: Decimal("0"), _CASILLA_44: Decimal("0")}
    absent: dict[CasillaId, Decimal] = {}

    for revision_id, revision in _m303_revisions():
        predicate = _sole_prorrata_predicate(revision_id, revision)
        assert evaluate_verification_predicates((predicate,), explicit_zero, _workflow_profile()) == [], revision_id
        assert evaluate_verification_predicates((predicate,), absent, _workflow_profile()) == [], revision_id
