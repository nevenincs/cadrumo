"""Calculation-revision replay and canonical-key contract tests."""

from __future__ import annotations

from decimal import Decimal
from typing import cast

import pytest
from pydantic import ValidationError

from ....core.casilla_id import CasillaId
from ..calculation_revision import CalculationRevision, CalculationRevisionState, derive_calculation_revision_id
from ..errors import ModeloValidationError
from ._calculation_revision_test_support import (
    _INPUT_CASILLA_001,
    _NONCANONICAL_CASILLA_KEY,
    _OUTPUT_CASILLA_002,
    _PAGOS_RELATION,
    _WHITESPACE_CASILLA_KEY,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def test_revision_id_changes_when_row_binding_value_changes() -> None:
    """A different row-indexed binding value must produce a different id."""
    id_a = derive_calculation_revision_id(
        work_unit_id="a" * 64,
        input_values_by_casilla_id={},
        binding_overrides={},
        row_binding_values={"modelo-720-asset-row-valuation": {"1": "60000"}},
        casilla_values={},
        filing_instance_evidence=None,
        source_provenance=(),
    )
    id_b = derive_calculation_revision_id(
        work_unit_id="a" * 64,
        input_values_by_casilla_id={},
        binding_overrides={},
        row_binding_values={"modelo-720-asset-row-valuation": {"1": "65000"}},
        casilla_values={},
        filing_instance_evidence=None,
        source_provenance=(),
    )
    assert id_a != id_b


def test_revision_id_normalises_row_binding_order() -> None:
    id_ordered = derive_calculation_revision_id(
        work_unit_id="a" * 64,
        input_values_by_casilla_id={},
        binding_overrides={},
        row_binding_values={
            "modelo-720-asset-row-class": {"1": "C", "2": "V"},
            "modelo-720-asset-row-valuation": {"1": "60000", "2": "55000"},
        },
        casilla_values={},
        filing_instance_evidence=None,
        source_provenance=(),
    )
    id_reversed = derive_calculation_revision_id(
        work_unit_id="a" * 64,
        input_values_by_casilla_id={},
        binding_overrides={},
        row_binding_values={
            "modelo-720-asset-row-valuation": {"2": "55000", "1": "60000"},
            "modelo-720-asset-row-class": {"2": "V", "1": "C"},
        },
        casilla_values={},
        filing_instance_evidence=None,
        source_provenance=(),
    )
    assert id_ordered == id_reversed


def test_revision_id_changes_when_relation_override_changes() -> None:
    """Relation replay values are part of the immutable calculation attempt."""
    id_a = derive_calculation_revision_id(
        work_unit_id="a" * 64,
        input_values_by_casilla_id={_INPUT_CASILLA_001: "10.00"},
        binding_overrides={},
        relation_overrides={_PAGOS_RELATION: "725.75"},
        casilla_values={_OUTPUT_CASILLA_002: Decimal("15.00")},
        filing_instance_evidence=None,
        source_provenance=(),
    )
    id_b = derive_calculation_revision_id(
        work_unit_id="a" * 64,
        input_values_by_casilla_id={_INPUT_CASILLA_001: "10.00"},
        binding_overrides={},
        relation_overrides={_PAGOS_RELATION: "725.76"},
        casilla_values={_OUTPUT_CASILLA_002: Decimal("15.00")},
        filing_instance_evidence=None,
        source_provenance=(),
    )
    assert id_a != id_b


def test_revision_id_derivation_rejects_non_canonical_casilla_keys() -> None:
    """Bad casilla keys must fail before a content-addressed revision id is minted."""
    with pytest.raises(ModeloValidationError, match=r"input_values_by_casilla_id contains non-canonical casilla\.id"):
        derive_calculation_revision_id(
            work_unit_id="a" * 64,
            input_values_by_casilla_id={_NONCANONICAL_CASILLA_KEY: "10.00"},
            binding_overrides={},
            casilla_values={_OUTPUT_CASILLA_002: Decimal("15.00")},
            filing_instance_evidence=None,
            source_provenance=(),
        )

    with pytest.raises(ModeloValidationError, match=r"casilla_values contains non-canonical casilla\.id"):
        derive_calculation_revision_id(
            work_unit_id="a" * 64,
            input_values_by_casilla_id={_INPUT_CASILLA_001: "10.00"},
            binding_overrides={},
            casilla_values={_NONCANONICAL_CASILLA_KEY: Decimal("15.00")},
            filing_instance_evidence=None,
            source_provenance=(),
        )

    with pytest.raises(ModeloValidationError, match=r"input_values_by_casilla_id contains non-canonical casilla\.id"):
        derive_calculation_revision_id(
            work_unit_id="a" * 64,
            input_values_by_casilla_id={_WHITESPACE_CASILLA_KEY: "10.00"},
            binding_overrides={},
            casilla_values={_OUTPUT_CASILLA_002: Decimal("15.00")},
            filing_instance_evidence=None,
            source_provenance=(),
        )

    with pytest.raises(ModeloValidationError, match=r"input_values_by_casilla_id contains non-canonical casilla\.id"):
        derive_calculation_revision_id(
            work_unit_id="a" * 64,
            input_values_by_casilla_id=cast("dict[CasillaId, str]", {1: "10.00"}),
            binding_overrides={},
            casilla_values={_OUTPUT_CASILLA_002: Decimal("15.00")},
            filing_instance_evidence=None,
            source_provenance=(),
        )

    with pytest.raises(ModeloValidationError, match=r"casilla_values contains non-canonical casilla\.id"):
        derive_calculation_revision_id(
            work_unit_id="a" * 64,
            input_values_by_casilla_id={_INPUT_CASILLA_001: "10.00"},
            binding_overrides={},
            casilla_values=cast("dict[CasillaId, Decimal]", {1: Decimal("15.00")}),
            filing_instance_evidence=None,
            source_provenance=(),
        )

    with pytest.raises(ModeloValidationError, match="binding_overrides contains non-canonical binding id"):
        derive_calculation_revision_id(
            work_unit_id="a" * 64,
            input_values_by_casilla_id={_INPUT_CASILLA_001: "10.00"},
            binding_overrides={"Bad Binding": "10.00"},
            casilla_values={_OUTPUT_CASILLA_002: Decimal("15.00")},
            filing_instance_evidence=None,
            source_provenance=(),
        )

    with pytest.raises(ModeloValidationError, match="relation_overrides contains non-canonical relation id"):
        derive_calculation_revision_id(
            work_unit_id="a" * 64,
            input_values_by_casilla_id={_INPUT_CASILLA_001: "10.00"},
            binding_overrides={},
            relation_overrides={"Bad Relation": "10.00"},
            casilla_values={_OUTPUT_CASILLA_002: Decimal("15.00")},
            filing_instance_evidence=None,
            source_provenance=(),
        )

    with pytest.raises(ModeloValidationError, match="row_binding_values contains non-canonical binding id"):
        derive_calculation_revision_id(
            work_unit_id="a" * 64,
            input_values_by_casilla_id={},
            binding_overrides={},
            row_binding_values={"Bad Binding": {"1": "C"}},
            casilla_values={},
            filing_instance_evidence=None,
            source_provenance=(),
        )

    with pytest.raises(ModeloValidationError, match="non-positive row index"):
        derive_calculation_revision_id(
            work_unit_id="a" * 64,
            input_values_by_casilla_id={},
            binding_overrides={},
            row_binding_values={"modelo-720-asset-row-class": {"0": "C"}},
            casilla_values={},
            filing_instance_evidence=None,
            source_provenance=(),
        )


def test_calculation_revision_rejects_persisted_non_canonical_casilla_keys() -> None:
    """A stored revision with malformed casilla keys must not construct."""
    from datetime import UTC, datetime

    created = datetime(2026, 5, 26, 10, 0, 0, tzinfo=UTC)
    with pytest.raises(ValidationError, match="String should match pattern"):
        CalculationRevision(
            calculation_revision_id="0" * 64,
            work_unit_id="a" * 64,
            state=CalculationRevisionState.BORRADOR,
            input_values_by_casilla_id={_NONCANONICAL_CASILLA_KEY: "10.00"},
            casilla_values={_OUTPUT_CASILLA_002: Decimal("15.00")},
            created_at=created,
            updated_at=created,
            filing_instance_evidence=None,
            source_provenance=(),
        )


def test_calculation_revision_rejects_legacy_inputs_snapshot_key() -> None:
    """Persisted revisions must use input_values_by_casilla_id, not inputs_snapshot."""
    from datetime import UTC, datetime

    created = datetime(2026, 5, 26, 10, 0, 0, tzinfo=UTC)
    output_values = {_OUTPUT_CASILLA_002: Decimal("15.00")}
    revision_id = derive_calculation_revision_id(
        work_unit_id="a" * 64,
        input_values_by_casilla_id={_INPUT_CASILLA_001: "10.00"},
        binding_overrides={},
        casilla_values=output_values,
        filing_instance_evidence=None,
        source_provenance=(),
    )
    with pytest.raises(ValidationError) as exc_info:
        CalculationRevision.model_validate(
            {
                "calculation_revision_id": revision_id,
                "work_unit_id": "a" * 64,
                "state": CalculationRevisionState.BORRADOR,
                "input_values_by_casilla_id": {_INPUT_CASILLA_001: "10.00"},
                "inputs_snapshot": {_INPUT_CASILLA_001: "10.00"},
                "casilla_values": output_values,
                "source_provenance": (),
                "created_at": created,
                "updated_at": created,
            },
        )

    message = str(exc_info.value)
    assert "inputs_snapshot" in message
    assert "Extra inputs are not permitted" in message


def test_calculation_revision_rejects_persisted_non_canonical_binding_keys() -> None:
    """A stored revision with malformed binding ids must not construct."""
    from datetime import UTC, datetime

    created = datetime(2026, 5, 26, 10, 0, 0, tzinfo=UTC)
    with pytest.raises(ValidationError, match="String should match pattern"):
        CalculationRevision(
            calculation_revision_id="0" * 64,
            work_unit_id="a" * 64,
            state=CalculationRevisionState.BORRADOR,
            binding_overrides={"Bad Binding": "10.00"},
            casilla_values={_OUTPUT_CASILLA_002: Decimal("15.00")},
            created_at=created,
            updated_at=created,
            filing_instance_evidence=None,
            source_provenance=(),
        )

    with pytest.raises(ValidationError, match="String should match pattern"):
        CalculationRevision(
            calculation_revision_id="0" * 64,
            work_unit_id="a" * 64,
            state=CalculationRevisionState.BORRADOR,
            bindings_sourced_from_borrador=("Bad Binding",),
            casilla_values={_OUTPUT_CASILLA_002: Decimal("15.00")},
            created_at=created,
            updated_at=created,
            filing_instance_evidence=None,
            source_provenance=(),
        )


def test_calculation_revision_normalises_row_binding_values() -> None:
    from datetime import UTC, datetime

    created = datetime(2026, 7, 5, 10, 0, 0, tzinfo=UTC)
    row_binding_values = {"modelo-720-asset-row-class": {"2": "V", "1": "C"}}
    revision_id = derive_calculation_revision_id(
        work_unit_id="a" * 64,
        input_values_by_casilla_id={},
        binding_overrides={},
        row_binding_values=row_binding_values,
        casilla_values={},
        filing_instance_evidence=None,
        source_provenance=(),
    )

    revision = CalculationRevision(
        calculation_revision_id=revision_id,
        work_unit_id="a" * 64,
        state=CalculationRevisionState.BORRADOR,
        input_values_by_casilla_id={},
        binding_overrides={},
        row_binding_values=row_binding_values,
        casilla_values={},
        created_at=created,
        updated_at=created,
        filing_instance_evidence=None,
        source_provenance=(),
    )

    assert revision.row_binding_values == {"modelo-720-asset-row-class": {"1": "C", "2": "V"}}


def test_calculation_revision_rejects_overlapping_binding_and_relation_replay_ids() -> None:
    """A replay id must belong to exactly one engine channel."""
    from datetime import UTC, datetime

    created = datetime(2026, 5, 26, 10, 0, 0, tzinfo=UTC)
    replay_id = "renta-2024-rel-130-pagos-fraccionados"
    revision_id = derive_calculation_revision_id(
        work_unit_id="a" * 64,
        input_values_by_casilla_id={},
        binding_overrides={replay_id: "1.00"},
        relation_overrides={replay_id: "1.00"},
        casilla_values={_OUTPUT_CASILLA_002: Decimal("15.00")},
        filing_instance_evidence=None,
        source_provenance=(),
    )
    with pytest.raises(ValidationError, match="replay ids must be channel-unique"):
        CalculationRevision(
            calculation_revision_id=revision_id,
            work_unit_id="a" * 64,
            state=CalculationRevisionState.BORRADOR,
            binding_overrides={replay_id: "1.00"},
            relation_overrides={replay_id: "1.00"},
            casilla_values={_OUTPUT_CASILLA_002: Decimal("15.00")},
            created_at=created,
            updated_at=created,
            filing_instance_evidence=None,
            source_provenance=(),
        )
