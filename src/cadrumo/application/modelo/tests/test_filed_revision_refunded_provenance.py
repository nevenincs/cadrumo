"""A refunded local Modelo 303 carry states only provenance it actually performed.

The local filing path re-stamps ``iva.compensacion-disponible-fin-periodo`` for a
refunded (devolución) period, because a refunded credit is not carried forward
(RD 1624/1992 art. 30 / Ley 37/1992 art. 116). The value it writes is the
posterior-only balance, which is NOT the registry formula's ``87 + generada``
projection -- that formula never ran for this figure.

The rewrite used to change only the value, leaving ``formula_id``,
``operand_refs`` and ``operand_values`` describing the addition it had just
overridden. The AEAT-capture sibling does the deliberate opposite: it refuses
outright when supplied refs disagree with the formula's projection. Two paths
therefore handled one case incompatibly, and the local one persisted a
provenance claim its own figure contradicted, all the way to the operator
surface.

These tests exercise the real rewrite and the real domain derivation. Nothing is
stubbed, and no figure is manufactured as a parity expectation: what is asserted
is the provenance SHAPE and the decomposition identity, both of which are
contracts rather than AEAT arithmetic.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from ....domain.calculations.registry import CasillaId, CasillaObservation
from ....domain.iva_compensation import derive_m303_compensation_available_from_casillas
from ...calculations import M303_DISPONIBLE_CASILLA, M303_GENERADA_CASILLA, M303_POSTERIOR_CASILLA
from .._filed_revision_observation import _refunded_303_observations

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_LEGAL_REFS = ("ley-37-1992:art-99",)
_SOURCE_REFS = ("aeat-manual-iva",)


def _computed(casilla_id: CasillaId, value: Decimal) -> CasillaObservation:
    """A row shaped as the engine emits a COMPUTED casilla, with full lineage."""
    return CasillaObservation(
        casilla_id=casilla_id,
        value=value,
        formula_id="modelo-303-compensacion-disponible-fin-periodo",
        op="add",
        operand_refs=(M303_POSTERIOR_CASILLA, M303_GENERADA_CASILLA),
        operand_casilla_refs=(M303_POSTERIOR_CASILLA, M303_GENERADA_CASILLA),
        operand_values=(Decimal("40.00"), Decimal("85.00")),
        legal_refs=_LEGAL_REFS,
        source_refs=_SOURCE_REFS,
    )


def _input_row(casilla_id: CasillaId, value: Decimal) -> CasillaObservation:
    return CasillaObservation(
        casilla_id=casilla_id,
        value=value,
        legal_refs=_LEGAL_REFS,
        source_refs=_SOURCE_REFS,
    )


def _filed_refunded_period() -> tuple[CasillaObservation, ...]:
    """A filed period declaring posterior 40, generada 85, disponible 125."""
    return (
        _input_row(M303_POSTERIOR_CASILLA, Decimal("40.00")),
        _computed(M303_GENERADA_CASILLA, Decimal("85.00")),
        _computed(M303_DISPONIBLE_CASILLA, Decimal("125.00")),
    )


def _by_id(observations: tuple[CasillaObservation, ...]) -> dict[CasillaId, CasillaObservation]:
    return {item.casilla_id: item for item in observations}


def test_refunded_available_row_drops_lineage_for_arithmetic_it_did_not_perform() -> None:
    """The re-stamped available row asserts no formula and no operands.

    Its value is the posterior-only balance, so the ``87 + generada`` addition
    the lineage named did not produce it. Leaving the lineage in place is the
    provenance contradiction the AEAT-capture path refuses.
    """
    rewritten = _by_id(_refunded_303_observations(_filed_refunded_period()))
    available = rewritten[M303_DISPONIBLE_CASILLA]

    assert available.value == Decimal("40.00")
    assert available.formula_id is None
    assert available.op is None
    assert available.operand_refs == ()
    assert available.operand_casilla_refs == ()
    assert available.operand_values == ()


def test_refunded_generada_row_is_zeroed_and_drops_its_lineage() -> None:
    """The excluded generated credit is zero, and states no formula for that zero."""
    rewritten = _by_id(_refunded_303_observations(_filed_refunded_period()))
    generada = rewritten[M303_GENERADA_CASILLA]

    assert generada.value == Decimal("0")
    assert generada.formula_id is None
    assert generada.op is None
    assert generada.operand_refs == ()
    assert generada.operand_values == ()


def test_the_rewrite_preserves_regulatory_grounding_on_every_row() -> None:
    """Dropping formula lineage must not drop legal or source provenance.

    ``legal_refs`` and ``source_refs`` answer WHY the casilla exists and must
    survive to the operator surface on every carried row; only the formula trace
    is untrue for a refunded period.
    """
    rewritten = _refunded_303_observations(_filed_refunded_period())

    assert rewritten
    for item in rewritten:
        assert item.legal_refs == _LEGAL_REFS
        assert item.source_refs == _SOURCE_REFS


def test_untouched_rows_keep_their_lineage_verbatim() -> None:
    """A casilla outside the compensation pair is carried through unchanged."""
    posterior_before = _by_id(_filed_refunded_period())[M303_POSTERIOR_CASILLA]
    posterior_after = _by_id(_refunded_303_observations(_filed_refunded_period()))[M303_POSTERIOR_CASILLA]

    assert posterior_after == posterior_before


def test_the_local_rewrite_states_the_shape_the_canonical_derivation_dictates() -> None:
    """The dropped lineage is the derivation's own answer, not a local decision.

    The domain derivation returns empty ``operand_refs`` for a refunded period
    precisely so its callers cannot claim the formula ran. The AEAT-capture path
    keys ``formula_id`` off that emptiness; this asserts the local path lands on
    the same shape, from the same authority, so the two cannot diverge.
    """
    derivation = derive_m303_compensation_available_from_casillas(
        {M303_POSTERIOR_CASILLA: Decimal("40.00"), M303_GENERADA_CASILLA: Decimal("85.00")},
        refunded=True,
    )
    assert derivation is not None
    assert derivation.operand_refs == ()
    assert derivation.operand_values == ()

    available = _by_id(_refunded_303_observations(_filed_refunded_period()))[M303_DISPONIBLE_CASILLA]

    assert available.value == derivation.available
    assert available.operand_refs == derivation.operand_refs
    assert available.operand_values == derivation.operand_values


def test_the_carried_pair_still_decomposes_after_the_rewrite() -> None:
    """``available == posterior + generated`` survives the refunded branch.

    The two fields are one decomposition, so a rewrite that corrected only one
    of them would persist a pair no reader could reconcile.
    """
    rewritten = _by_id(_refunded_303_observations(_filed_refunded_period()))

    assert (
        rewritten[M303_DISPONIBLE_CASILLA].value
        == rewritten[M303_POSTERIOR_CASILLA].value + rewritten[M303_GENERADA_CASILLA].value
    )


def test_an_undeclared_posterior_box_carries_nothing_forward() -> None:
    """With no box 87 declared there is no posterior credit to survive the refund."""
    observations = (_computed(M303_DISPONIBLE_CASILLA, Decimal("85.00")),)

    rewritten = _by_id(_refunded_303_observations(observations))

    assert rewritten[M303_DISPONIBLE_CASILLA].value == Decimal("0")
    assert rewritten[M303_DISPONIBLE_CASILLA].formula_id is None
