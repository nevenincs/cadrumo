"""A revision records its operator layer without moving any stored revision id.

The layer is additive and optional: absent means UNKNOWN. A revision stored
before it existed loads unchanged and re-derives the id it was stored under,
which is pinned here from the derivation as it stood before the layer. A
recorded layer, even an empty one, joins the identity, so a revision that
knows its caller tier never collides with one that does not.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from decimal import Decimal

import pytest
from pydantic import ValidationError

from ....core.casilla_id import CasillaId, validated_casilla_id
from ...calculations.registry.bindings import CasillaObservation
from ...calculations.registry.schema_references import RegistrySnapshotRef
from ..calculation_revision import (
    CalculationRevision,
    CalculationRevisionState,
    derive_calculation_revision_id,
    derive_calculation_revision_id_from_revision,
)
from ..calculation_revision_operator_layer import CalculationOperatorLayer

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

#: Derived for the inputs below by the revision-id derivation before the
#: operator layer existed; a stored revision's id must not move.
_PINNED_ID_WITHOUT_OPERATOR_LAYER = "68302bf28b2c55ca4a6f1e34777bbff916eb8b5c593167e10d7d2e31ea3ec4e8"
_WORK_UNIT_ID = "b" * 64
_C06: CasillaId = validated_casilla_id("06")
_C07: CasillaId = validated_casilla_id("07")
_C08: CasillaId = validated_casilla_id("08")
_C09: CasillaId = validated_casilla_id("09")
_BINDING = "modelo-130-pagos-fraccionados-anteriores"
_SNAPSHOT_REF = RegistrySnapshotRef(modelo="130", revision_id="2019-y-siguientes", modelo_year=2026, period="1T")
_CREATED = datetime(2026, 4, 1, 9, 0, tzinfo=UTC)


def _revision_id(operator_layer: CalculationOperatorLayer | None) -> str:
    return derive_calculation_revision_id(
        work_unit_id=_WORK_UNIT_ID,
        input_values_by_casilla_id={_C06: "100", _C08: "texto"},
        binding_overrides={_BINDING: "0"},
        casilla_values={_C06: Decimal("100"), _C07: Decimal("-100.00")},
        filing_instance_evidence=None,
        source_provenance=(),
        cleared_casilla_ids=(_C09,),
        operator_layer=operator_layer,
    )


def _observation(casilla_id: CasillaId, value: Decimal) -> CasillaObservation:
    return CasillaObservation(
        casilla_id=casilla_id,
        value=value,
        legal_refs=("ley-35-2006:art-99",),
        source_refs=("aeat-dr-130",),
    )


def _revision(operator_layer: CalculationOperatorLayer | None) -> CalculationRevision:
    return CalculationRevision(
        calculation_revision_id=_revision_id(operator_layer),
        work_unit_id=_WORK_UNIT_ID,
        registry_snapshot_ref=_SNAPSHOT_REF,
        state=CalculationRevisionState.BORRADOR,
        input_values_by_casilla_id={_C06: "100", _C08: "texto"},
        binding_overrides={_BINDING: "0"},
        casilla_values={_C06: Decimal("100"), _C07: Decimal("-100.00")},
        observations=(_observation(_C06, Decimal("100")), _observation(_C07, Decimal("-100.00"))),
        cleared_casilla_ids=(_C09,),
        operator_layer=operator_layer,
        filing_instance_evidence=None,
        source_provenance=(),
        created_at=_CREATED,
        updated_at=_CREATED,
    )


_LAYER = CalculationOperatorLayer(
    decimal_casilla_inputs={_C06: "100"},
    text_casilla_inputs={_C08: "texto"},
    binding_overrides={_BINDING: "0"},
)


def test_a_revision_without_an_operator_layer_keeps_the_id_it_was_stored_under() -> None:
    assert _revision_id(None) == _PINNED_ID_WITHOUT_OPERATOR_LAYER


def test_a_recorded_operator_layer_joins_the_identity_even_when_empty() -> None:
    empty = _revision_id(CalculationOperatorLayer())
    recorded = _revision_id(_LAYER)

    assert empty != _PINNED_ID_WITHOUT_OPERATOR_LAYER
    assert recorded != _PINNED_ID_WITHOUT_OPERATOR_LAYER
    assert recorded != empty
    assert recorded == _revision_id(_LAYER)


def test_the_identity_is_blind_to_the_order_the_operator_supplied_values_in() -> None:
    reordered = CalculationOperatorLayer(
        decimal_casilla_inputs={_C07: "5", _C06: "100"},
    )
    ordered = CalculationOperatorLayer(
        decimal_casilla_inputs={_C06: "100", _C07: "5"},
    )

    assert _revision_id(reordered) == _revision_id(ordered)


def test_a_stored_revision_without_the_field_loads_as_unknown_and_re_derives_its_id() -> None:
    stored = json.loads(_revision(None).model_dump_json())
    del stored["operator_layer"]

    loaded = CalculationRevision.model_validate_json(json.dumps(stored))

    assert loaded.operator_layer is None
    assert loaded.calculation_revision_id == _PINNED_ID_WITHOUT_OPERATOR_LAYER
    assert derive_calculation_revision_id_from_revision(loaded) == _PINNED_ID_WITHOUT_OPERATOR_LAYER


def test_a_revision_with_a_layer_round_trips_it() -> None:
    revision = _revision(_LAYER)

    loaded = CalculationRevision.model_validate_json(revision.model_dump_json())

    assert loaded == revision
    assert loaded.operator_layer == _LAYER
    assert derive_calculation_revision_id_from_revision(loaded) == revision.calculation_revision_id


def test_an_operator_value_and_an_explicit_clear_of_one_casilla_are_refused_together() -> None:
    layer = CalculationOperatorLayer(decimal_casilla_inputs={_C09: "1"})

    with pytest.raises(ValidationError, match="also records as cleared"):
        _revision(layer)


@pytest.mark.parametrize("raw", ["1.50", "1e3", "NaN", "1,5", "+1", " 1"])
def test_a_decimal_input_must_be_the_canonical_decimal_string(raw: str) -> None:
    with pytest.raises(ValidationError, match="canonical decimal"):
        CalculationOperatorLayer(decimal_casilla_inputs={_C06: raw})


def test_one_casilla_cannot_reach_both_channels() -> None:
    with pytest.raises(ValidationError, match="exactly one channel"):
        CalculationOperatorLayer(decimal_casilla_inputs={_C06: "1"}, text_casilla_inputs={_C06: "1"})


def test_an_empty_layer_is_known_and_empty() -> None:
    assert CalculationOperatorLayer().is_empty
    assert not _LAYER.is_empty
    assert _LAYER.casilla_ids() == frozenset({_C06, _C08})
