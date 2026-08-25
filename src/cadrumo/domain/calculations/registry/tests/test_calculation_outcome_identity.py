"""One outcome per casilla in a registry calculation result.

:class:`RegistryCalculationResult` projects its typed rows into a mapping
keyed by ``casilla_id`` (:attr:`RegistryCalculationResult.values`). A mapping
cannot represent two rows for one key, so a repeated casilla would resolve by
position — the last row wins and the earlier row's value and provenance are
lost with no refusal. Its resolved and unresolved channels are the same hazard
across two collections: a casilla carrying both a Decimal and a blocking
unresolved reason makes ``values`` and verification report contradictory
truths about one filing.

The engine builds a calculation result's observations from a mapping, so
uniqueness holds there by construction today; these gates make it a stated
contract of the envelope rather than an accident of one producer.

:class:`~domain.calculations.registry.RegistryModeloObservation` is
deliberately NOT under the same rule. Multi-row informativas repeat a casilla
once per declared item, so its ordered tuple is the multiplicity carrier and a
uniqueness refusal there would reject correct filings; that contract is pinned
below as preservation.

Anti-tautology: each duplicate case uses two DIFFERENT values (``1`` and
``999``) and each valid counterpart asserts the surviving values, so a guard
that silently collapsed rows instead of refusing would surface as the wrong
value rather than as a pass.
"""

from __future__ import annotations

from decimal import Decimal

import pytest
from pydantic import ValidationError

from .....core import CasillaId, validated_casilla_id
from ..bindings import CasillaObservation, RegistryModeloObservation
from ..formula_runtime import RegistryCalculationResult, RegistryCalculationUnresolvedOutcome
from ..formula_runtime_ops import RegistryUnresolvedOutcomeReason
from ..ids import LegalRefId, SourceRefId

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


_CONTESTED_CASILLA: CasillaId = validated_casilla_id("iva.cuota-devengada-total")
_OTHER_CASILLA: CasillaId = validated_casilla_id("iva.cuota-deducible-total")
_LEGAL_REFS: tuple[LegalRefId, ...] = ("ley-37-1992:art-21",)
_SOURCE_REFS: tuple[SourceRefId, ...] = ("aeat-iva-2025",)

_EARLIER_VALUE = Decimal("1")
_LATER_VALUE = Decimal("999")


def _observation(casilla_id: CasillaId, value: Decimal) -> CasillaObservation:
    return CasillaObservation(
        casilla_id=casilla_id,
        value=value,
        legal_refs=_LEGAL_REFS,
        source_refs=_SOURCE_REFS,
    )


def _unresolved(casilla_id: CasillaId) -> RegistryCalculationUnresolvedOutcome:
    return RegistryCalculationUnresolvedOutcome(
        casilla_id=casilla_id,
        reason=RegistryUnresolvedOutcomeReason.M210_CONVENIO_RATE_MISSING,
        formula_id="iva.formula.devengada",
        op="add",
        legal_refs=_LEGAL_REFS,
        source_refs=_SOURCE_REFS,
    )


# ---------------------------------------------------------------------------
# RegistryModeloObservation — repetition is the detail-row contract
# ---------------------------------------------------------------------------


def test_filed_observation_keeps_repeated_detail_rows_in_order() -> None:
    """A filed observation MUST keep repeated rows; multiplicity is the payload.

    Multi-row informativas (Modelo 720 bienes en el extranjero, Modelo 721
    monedas virtuales) declare one row per declared item, so the same casilla
    id legitimately repeats and the ORDER carries which value belongs to which
    item. The ordered ``observations`` tuple is canonical for these domains and
    ``casilla_values`` is a documented lossy convenience view — a uniqueness
    refusal here would reject correct filings, so the contract pinned is
    preservation, not refusal.
    """
    observation = RegistryModeloObservation(
        modelo="130",
        filing_year=2026,
        period="1T",
        observations=(
            _observation(_CONTESTED_CASILLA, _EARLIER_VALUE),
            _observation(_CONTESTED_CASILLA, _LATER_VALUE),
        ),
    )

    assert tuple(item.value for item in observation.observations) == (_EARLIER_VALUE, _LATER_VALUE)
    # The mapping view collapses by design; the ordered tuple above is where
    # the second row survives.
    assert observation.casilla_values[_CONTESTED_CASILLA] == _LATER_VALUE


# ---------------------------------------------------------------------------
# RegistryCalculationResult — resolved rows
# ---------------------------------------------------------------------------


def test_calculation_result_refuses_duplicate_observation_rows() -> None:
    with pytest.raises(ValidationError) as raised:
        RegistryCalculationResult(
            modelo="130",
            revision="2019-y-siguientes",
            observations=(
                _observation(_CONTESTED_CASILLA, _EARLIER_VALUE),
                _observation(_CONTESTED_CASILLA, _LATER_VALUE),
            ),
        )

    assert _CONTESTED_CASILLA in str(raised.value)


def test_calculation_result_refuses_duplicate_unresolved_rows() -> None:
    with pytest.raises(ValidationError) as raised:
        RegistryCalculationResult(
            modelo="130",
            revision="2019-y-siguientes",
            unresolved_outcomes=(
                _unresolved(_CONTESTED_CASILLA),
                _unresolved(_CONTESTED_CASILLA),
            ),
        )

    assert _CONTESTED_CASILLA in str(raised.value)


def test_calculation_result_accepts_distinct_observation_rows() -> None:
    result = RegistryCalculationResult(
        modelo="130",
        revision="2019-y-siguientes",
        observations=(
            _observation(_CONTESTED_CASILLA, _EARLIER_VALUE),
            _observation(_OTHER_CASILLA, _LATER_VALUE),
        ),
    )

    assert dict(result.values) == {
        _CONTESTED_CASILLA: _EARLIER_VALUE,
        _OTHER_CASILLA: _LATER_VALUE,
    }


# ---------------------------------------------------------------------------
# RegistryCalculationResult — channel disjointness
# ---------------------------------------------------------------------------


def test_calculation_result_refuses_resolved_and_unresolved_for_one_casilla() -> None:
    """A casilla must not carry both a Decimal value and a blocking reason."""
    with pytest.raises(ValidationError) as raised:
        RegistryCalculationResult(
            modelo="130",
            revision="2019-y-siguientes",
            observations=(_observation(_CONTESTED_CASILLA, _LATER_VALUE),),
            unresolved_outcomes=(_unresolved(_CONTESTED_CASILLA),),
        )

    assert _CONTESTED_CASILLA in str(raised.value)


def test_calculation_result_accepts_disjoint_resolved_and_unresolved_casillas() -> None:
    """Different casillas may resolve and block independently."""
    result = RegistryCalculationResult(
        modelo="130",
        revision="2019-y-siguientes",
        observations=(_observation(_OTHER_CASILLA, _LATER_VALUE),),
        unresolved_outcomes=(_unresolved(_CONTESTED_CASILLA),),
    )

    assert dict(result.values) == {_OTHER_CASILLA: _LATER_VALUE}
    assert result.unresolved_outcomes[0].casilla_id == _CONTESTED_CASILLA
    assert _CONTESTED_CASILLA not in result.values
