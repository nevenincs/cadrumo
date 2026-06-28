"""Calculation revision identity contract tests."""

from __future__ import annotations

from decimal import Decimal
from typing import cast

import pytest
from pydantic import ValidationError

from ...calculations.registry import CasillaId, RelationId, validated_casilla_id
from .._calculation_revision import CalculationRevision, CalculationRevisionState, derive_calculation_revision_id
from .._errors import ModeloValidationError

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]



def _casilla_id(value: object) -> CasillaId:
    try:
        return validated_casilla_id(value, surface="test casilla id")
    except ValueError as exc:
        raise AssertionError(f"test fixture casilla key {value!r} is not a canonical casilla.id") from exc


_INPUT_CASILLA_001: CasillaId = _casilla_id("001")
_INPUT_CASILLA_002: CasillaId = _casilla_id("002")
_PIN_INPUT_CASILLA_01: CasillaId = _casilla_id("01")
_PIN_INPUT_CASILLA_02: CasillaId = _casilla_id("02")
_PIN_INPUT_CASILLA_03: CasillaId = _casilla_id("03")
_OUTPUT_CASILLA_002: CasillaId = _casilla_id("002")
_PIN_OUTPUT_CASILLA_04: CasillaId = _casilla_id("04")
_PIN_OUTPUT_CASILLA_07: CasillaId = _casilla_id("07")
_PIN_OUTPUT_CASILLA_19: CasillaId = _casilla_id("19")
_OBSERVATION_CASILLA_100: CasillaId = _casilla_id("100")
_OBSERVATION_CASILLA_200: CasillaId = _casilla_id("200")
_ORDERED_OUTPUT_CASILLA_010: CasillaId = _casilla_id("010")
_ORDERED_OUTPUT_CASILLA_020: CasillaId = _casilla_id("020")
_PAGOS_RELATION: RelationId = "renta-2024-rel-130-pagos-fraccionados"
_NONCANONICAL_CASILLA_KEY = "bad key"
_WHITESPACE_CASILLA_KEY = " 001 "
_TEST_LEGAL_REFS = ("ley-58-2003:art-93",)
_TEST_SOURCE_REFS = ("aeat-dr-303-2025",)


def _base_id() -> str:
    return derive_calculation_revision_id(
        work_unit_id="a" * 64,
        input_values_by_casilla_id={_INPUT_CASILLA_001: "10.00"},
        binding_overrides={},
        casilla_values={_OUTPUT_CASILLA_002: Decimal("15.00")},
    )


def test_revision_id_is_stable_across_equal_inputs() -> None:
    """Same inputs must always yield the same id (content-addressing contract)."""
    first = _base_id()
    second = _base_id()
    assert first == second
    assert len(first) == 64
    assert first == first.lower()


def test_revision_id_pinned_against_fully_populated_fixture() -> None:
    """Anti-tautology proof: pin the exact SHA-256 for a fully-populated
    derivation against a known-good hex string.

    Staged for linkage cleanup (the planned collapse of
    ``CalculationRevision.casilla_values`` into a derived ``@property``
    over the typed ``observations`` envelope). The collapse must
    preserve the hash domain — every already-persisted revision id
    must still derive identically after the field-shape change, or
    every catalogue row gets a phantom mismatch and the
    content-addressing contract breaks.

    The fixture sets every defaultable parameter to a non-default
    value so the pin exercises every branch of the hash payload:
    inputs, overrides, outputs, source_transaction_ids,
    borrador_snapshot_id, and bindings_sourced_from_borrador.

    Update procedure: if a future change to the hash domain is
    explicitly intended (e.g. a migration-bumping schema rev), update
    the pinned hex in tandem with the change and document the
    migration. If this test fails without an explicit hash-domain
    change, the regression is in the hash derivation itself.
    """
    pinned = "5b78dd04e614a50fe448439b7fdb843f1e31afe76f9d424d0276866679dee7ca"
    derived = derive_calculation_revision_id(
        work_unit_id="b" * 64,
        input_values_by_casilla_id={
            _PIN_INPUT_CASILLA_01: "1000.00",
            _PIN_INPUT_CASILLA_02: "250.00",
            _PIN_INPUT_CASILLA_03: "50.00",
        },
        binding_overrides={
            "previous_year_net_income": "13000.00",
            "profile.iva_regime": "GENERAL",
        },
        casilla_values={
            _PIN_OUTPUT_CASILLA_04: Decimal("1300.00"),
            _PIN_OUTPUT_CASILLA_07: Decimal("-50.50"),
            _PIN_OUTPUT_CASILLA_19: Decimal("200.25"),
        },
        source_transaction_ids=("a" * 64, "c" * 64),
        borrador_snapshot_id="borrador-2026-q1-snapshot",
        bindings_sourced_from_borrador=(
            "iva.aggregation",
            "renta.expense.aggregation",
        ),
    )
    assert derived == pinned, (
        f"Hash domain shifted — derive_calculation_revision_id returned "
        f"{derived!r} for a fully-populated fixture but the pinned value "
        f"is {pinned!r}. Every persisted CalculationRevision id now mismatches "
        f"its derived form; either revert the hash change or run a migration "
        f"and update the pin."
    )


def test_revision_id_changes_when_input_casilla_value_changes() -> None:
    """A different input_values_by_casilla_id must produce a different id."""
    id_a = derive_calculation_revision_id(
        work_unit_id="a" * 64,
        input_values_by_casilla_id={_INPUT_CASILLA_001: "10.00"},
        binding_overrides={},
        casilla_values={_OUTPUT_CASILLA_002: Decimal("15.00")},
    )
    id_b = derive_calculation_revision_id(
        work_unit_id="a" * 64,
        input_values_by_casilla_id={_INPUT_CASILLA_001: "99.00"},
        binding_overrides={},
        casilla_values={_OUTPUT_CASILLA_002: Decimal("15.00")},
    )
    assert id_a != id_b


def test_revision_id_changes_when_output_casilla_value_changes() -> None:
    """A different casilla_values mapping must produce a different id."""
    id_a = derive_calculation_revision_id(
        work_unit_id="a" * 64,
        input_values_by_casilla_id={_INPUT_CASILLA_001: "10.00"},
        binding_overrides={},
        casilla_values={_OUTPUT_CASILLA_002: Decimal("15.00")},
    )
    id_b = derive_calculation_revision_id(
        work_unit_id="a" * 64,
        input_values_by_casilla_id={_INPUT_CASILLA_001: "10.00"},
        binding_overrides={},
        casilla_values={_OUTPUT_CASILLA_002: Decimal("16.00")},
    )
    assert id_a != id_b


def test_revision_id_changes_when_work_unit_id_changes() -> None:
    """A different parent work_unit_id must produce a different id."""
    id_a = derive_calculation_revision_id(
        work_unit_id="a" * 64,
        input_values_by_casilla_id={_INPUT_CASILLA_001: "10.00"},
        binding_overrides={},
        casilla_values={_OUTPUT_CASILLA_002: Decimal("15.00")},
    )
    id_b = derive_calculation_revision_id(
        work_unit_id="b" * 64,
        input_values_by_casilla_id={_INPUT_CASILLA_001: "10.00"},
        binding_overrides={},
        casilla_values={_OUTPUT_CASILLA_002: Decimal("15.00")},
    )
    assert id_a != id_b


def test_revision_id_changes_when_relation_override_changes() -> None:
    """Relation replay values are part of the immutable calculation attempt."""
    id_a = derive_calculation_revision_id(
        work_unit_id="a" * 64,
        input_values_by_casilla_id={_INPUT_CASILLA_001: "10.00"},
        binding_overrides={},
        relation_overrides={_PAGOS_RELATION: "725.75"},
        casilla_values={_OUTPUT_CASILLA_002: Decimal("15.00")},
    )
    id_b = derive_calculation_revision_id(
        work_unit_id="a" * 64,
        input_values_by_casilla_id={_INPUT_CASILLA_001: "10.00"},
        binding_overrides={},
        relation_overrides={_PAGOS_RELATION: "725.76"},
        casilla_values={_OUTPUT_CASILLA_002: Decimal("15.00")},
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
        )

    with pytest.raises(ModeloValidationError, match=r"casilla_values contains non-canonical casilla\.id"):
        derive_calculation_revision_id(
            work_unit_id="a" * 64,
            input_values_by_casilla_id={_INPUT_CASILLA_001: "10.00"},
            binding_overrides={},
            casilla_values={_NONCANONICAL_CASILLA_KEY: Decimal("15.00")},
        )

    with pytest.raises(ModeloValidationError, match=r"input_values_by_casilla_id contains non-canonical casilla\.id"):
        derive_calculation_revision_id(
            work_unit_id="a" * 64,
            input_values_by_casilla_id={_WHITESPACE_CASILLA_KEY: "10.00"},
            binding_overrides={},
            casilla_values={_OUTPUT_CASILLA_002: Decimal("15.00")},
        )

    with pytest.raises(ModeloValidationError, match=r"input_values_by_casilla_id contains non-canonical casilla\.id"):
        derive_calculation_revision_id(
            work_unit_id="a" * 64,
            input_values_by_casilla_id=cast("dict[CasillaId, str]", {1: "10.00"}),
            binding_overrides={},
            casilla_values={_OUTPUT_CASILLA_002: Decimal("15.00")},
        )

    with pytest.raises(ModeloValidationError, match=r"casilla_values contains non-canonical casilla\.id"):
        derive_calculation_revision_id(
            work_unit_id="a" * 64,
            input_values_by_casilla_id={_INPUT_CASILLA_001: "10.00"},
            binding_overrides={},
            casilla_values=cast("dict[CasillaId, Decimal]", {1: Decimal("15.00")}),
        )

    with pytest.raises(ModeloValidationError, match="binding_overrides contains non-canonical binding id"):
        derive_calculation_revision_id(
            work_unit_id="a" * 64,
            input_values_by_casilla_id={_INPUT_CASILLA_001: "10.00"},
            binding_overrides={"Bad Binding": "10.00"},
            casilla_values={_OUTPUT_CASILLA_002: Decimal("15.00")},
        )

    with pytest.raises(ModeloValidationError, match="relation_overrides contains non-canonical relation id"):
        derive_calculation_revision_id(
            work_unit_id="a" * 64,
            input_values_by_casilla_id={_INPUT_CASILLA_001: "10.00"},
            binding_overrides={},
            relation_overrides={"Bad Relation": "10.00"},
            casilla_values={_OUTPUT_CASILLA_002: Decimal("15.00")},
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
        )


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
        )


def test_observations_consistency_validator_accepts_matching_projection() -> None:
    """Stage one of the staged consistency check: when observations is populated, casilla_values
    must equal the projection of observations. Matching pair validates clean."""
    from datetime import UTC, datetime

    from ...calculations.registry import CasillaObservation
    from .._calculation_revision import CalculationRevision, CalculationRevisionState

    work_unit_id = "d" * 64
    casilla_values = {
        _OBSERVATION_CASILLA_100: Decimal("250.00"),
        _OBSERVATION_CASILLA_200: Decimal("-75.50"),
    }
    observations = (
        CasillaObservation(
            casilla_id=_OBSERVATION_CASILLA_100,
            value=Decimal("250.00"),
            legal_refs=_TEST_LEGAL_REFS,
            source_refs=_TEST_SOURCE_REFS,
        ),
        CasillaObservation(
            casilla_id=_OBSERVATION_CASILLA_200,
            value=Decimal("-75.50"),
            legal_refs=_TEST_LEGAL_REFS,
            source_refs=_TEST_SOURCE_REFS,
        ),
    )
    revision_id = derive_calculation_revision_id(
        work_unit_id=work_unit_id,
        input_values_by_casilla_id={},
        binding_overrides={},
        casilla_values=casilla_values,
    )
    created = datetime(2026, 5, 26, 10, 0, 0, tzinfo=UTC)
    rev = CalculationRevision(
        calculation_revision_id=revision_id,
        work_unit_id=work_unit_id,
        state=CalculationRevisionState.BORRADOR,
        casilla_values=casilla_values,
        observations=observations,
        created_at=created,
        updated_at=created,
    )
    assert rev.observations == observations
    assert dict(rev.casilla_values) == casilla_values


def test_observations_consistency_validator_rejects_drift() -> None:
    """Stage one of the staged consistency check: when observations diverges from casilla_values,
    construction must raise ModeloValidationError — save/load drift surfaces at
    load time rather than at a downstream hash mismatch."""
    from datetime import UTC, datetime

    import pydantic

    from ...calculations.registry import CasillaObservation
    from .._calculation_revision import CalculationRevision, CalculationRevisionState

    work_unit_id = "e" * 64
    casilla_values = {_OBSERVATION_CASILLA_100: Decimal("250.00")}
    # observations encodes a DIFFERENT value for the same casilla — the
    # validator must refuse to construct.
    observations = (
        CasillaObservation(
            casilla_id=_OBSERVATION_CASILLA_100,
            value=Decimal("999.99"),
            legal_refs=_TEST_LEGAL_REFS,
            source_refs=_TEST_SOURCE_REFS,
        ),
    )
    revision_id = derive_calculation_revision_id(
        work_unit_id=work_unit_id,
        input_values_by_casilla_id={},
        binding_overrides={},
        casilla_values=casilla_values,
    )
    created = datetime(2026, 5, 26, 10, 0, 0, tzinfo=UTC)
    with pytest.raises(pydantic.ValidationError, match="inconsistent with the typed observations envelope"):
        CalculationRevision(
            calculation_revision_id=revision_id,
            work_unit_id=work_unit_id,
            state=CalculationRevisionState.BORRADOR,
            casilla_values=casilla_values,
            observations=observations,
            created_at=created,
            updated_at=created,
        )


def test_observations_consistency_validator_rejects_non_empty_values_without_observations() -> None:
    """A non-empty flat value map without typed observations is an incomplete revision."""
    from datetime import UTC, datetime

    import pydantic

    from .._calculation_revision import CalculationRevision, CalculationRevisionState

    work_unit_id = "f" * 64
    casilla_values = {_OBSERVATION_CASILLA_100: Decimal("250.00")}
    revision_id = derive_calculation_revision_id(
        work_unit_id=work_unit_id,
        input_values_by_casilla_id={},
        binding_overrides={},
        casilla_values=casilla_values,
    )
    created = datetime(2026, 5, 26, 10, 0, 0, tzinfo=UTC)
    with pytest.raises(pydantic.ValidationError, match="must carry typed observations"):
        CalculationRevision(
            calculation_revision_id=revision_id,
            work_unit_id=work_unit_id,
            state=CalculationRevisionState.BORRADOR,
            casilla_values=casilla_values,
            created_at=created,
            updated_at=created,
        )


def test_revision_id_is_insensitive_to_dict_key_insertion_order() -> None:
    """Dict key ordering must not affect the derived id (sort_keys guarantee)."""
    id_ordered = derive_calculation_revision_id(
        work_unit_id="c" * 64,
        input_values_by_casilla_id={_INPUT_CASILLA_001: "1.00", _INPUT_CASILLA_002: "2.00"},
        binding_overrides={},
        casilla_values={
            _ORDERED_OUTPUT_CASILLA_010: Decimal("5.00"),
            _ORDERED_OUTPUT_CASILLA_020: Decimal("6.00"),
        },
    )
    id_reversed = derive_calculation_revision_id(
        work_unit_id="c" * 64,
        input_values_by_casilla_id={_INPUT_CASILLA_002: "2.00", _INPUT_CASILLA_001: "1.00"},
        binding_overrides={},
        casilla_values={
            _ORDERED_OUTPUT_CASILLA_020: Decimal("6.00"),
            _ORDERED_OUTPUT_CASILLA_010: Decimal("5.00"),
        },
    )
    assert id_ordered == id_reversed


def test_revision_id_includes_present_borrador_metadata() -> None:
    """Adding borrador metadata to otherwise-identical inputs must change the id."""
    base = derive_calculation_revision_id(
        work_unit_id="b" * 64,
        input_values_by_casilla_id={_INPUT_CASILLA_001: "10.00"},
        binding_overrides={},
        casilla_values={_OUTPUT_CASILLA_002: Decimal("15.00")},
    )
    with_borrador = derive_calculation_revision_id(
        work_unit_id="b" * 64,
        input_values_by_casilla_id={_INPUT_CASILLA_001: "10.00"},
        binding_overrides={},
        casilla_values={_OUTPUT_CASILLA_002: Decimal("15.00")},
        borrador_snapshot_id="snapshot-100-2025",
        bindings_sourced_from_borrador=("casilla_001",),
    )

    assert with_borrador != base


def test_detail_rows_sort_key_handles_all_four_row_types() -> None:
    """Regression: sort key must work for all four row types (M184/M232 use nif,
    M349 uses nif_comunitario, M347 uses nif). This test verifies the sort key
    accessor correctly extracts the identifier field for each row type."""
    from .._row_models import (
        Modelo184MemberRow,
        Modelo232VinculadaRow,
        Modelo347ContraparteRow,
        Modelo349OperadorRow,
    )

    # Create one row of each type with distinct nif/nif_comunitario values.
    m184_row = Modelo184MemberRow(nif="12345678A", porcentaje=Decimal("50.00"), importe=Decimal("100.00"))
    m232_row = Modelo232VinculadaRow(nif="87654321B", importe=Decimal("200.00"))
    m349_row = Modelo349OperadorRow(
        codigo_pais="DE",
        nif_comunitario="DE123456789",
        clave_operacion="E",
        importe=Decimal("300.00"),
    )
    m347_row = Modelo347ContraparteRow(nif="11223344C", importe_Q1=Decimal("400.00"))

    # All four rows must flow through the hash derivation without AttributeError.
    # The sort should succeed and the hash should be deterministic.
    id1 = derive_calculation_revision_id(
        work_unit_id="a" * 64,
        input_values_by_casilla_id={},
        binding_overrides={},
        casilla_values={},
        detail_rows=(m184_row, m232_row, m349_row, m347_row),
    )
    # Same rows in reverse order must produce the same id (sort-insensitive).
    id2 = derive_calculation_revision_id(
        work_unit_id="a" * 64,
        input_values_by_casilla_id={},
        binding_overrides={},
        casilla_values={},
        detail_rows=(m347_row, m349_row, m232_row, m184_row),
    )
    assert id1 == id2, "Row sort key must handle all four row types consistently"
