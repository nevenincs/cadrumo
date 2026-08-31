"""Calculation-revision observation and detail-row contract tests."""

from __future__ import annotations

from decimal import Decimal

import pytest

from ..calculation_revision import derive_calculation_revision_id
from ._calculation_revision_test_support import (
    _INPUT_CASILLA_001,
    _INPUT_CASILLA_002,
    _OBSERVATION_CASILLA_100,
    _OBSERVATION_CASILLA_200,
    _ORDERED_OUTPUT_CASILLA_010,
    _ORDERED_OUTPUT_CASILLA_020,
    _OUTPUT_CASILLA_002,
    _TEST_LEGAL_REFS,
    _TEST_SOURCE_REFS,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def test_observations_consistency_validator_accepts_matching_projection() -> None:
    """Stage one of the staged consistency check: when observations is populated, casilla_values
    must equal the projection of observations. Matching pair validates clean."""
    from datetime import UTC, datetime

    from ...calculations.registry.bindings import CasillaObservation
    from ..calculation_revision import CalculationRevision, CalculationRevisionState

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
        filing_instance_evidence=None,
        source_provenance=(),
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
        filing_instance_evidence=None,
        source_provenance=(),
    )
    assert rev.observations == observations
    assert dict(rev.casilla_values) == casilla_values


def test_observations_consistency_validator_rejects_drift() -> None:
    """Stage one of the staged consistency check: when observations diverges from casilla_values,
    construction must raise ModeloValidationError — save/load drift surfaces at
    load time rather than at a downstream hash mismatch."""
    from datetime import UTC, datetime

    import pydantic

    from ...calculations.registry.bindings import CasillaObservation
    from ..calculation_revision import CalculationRevision, CalculationRevisionState

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
        filing_instance_evidence=None,
        source_provenance=(),
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
            filing_instance_evidence=None,
            source_provenance=(),
        )


def test_observations_consistency_validator_rejects_non_empty_values_without_observations() -> None:
    """A non-empty flat value map without typed observations is an incomplete revision."""
    from datetime import UTC, datetime

    import pydantic

    from ..calculation_revision import CalculationRevision, CalculationRevisionState

    work_unit_id = "f" * 64
    casilla_values = {_OBSERVATION_CASILLA_100: Decimal("250.00")}
    revision_id = derive_calculation_revision_id(
        work_unit_id=work_unit_id,
        input_values_by_casilla_id={},
        binding_overrides={},
        casilla_values=casilla_values,
        filing_instance_evidence=None,
        source_provenance=(),
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
            filing_instance_evidence=None,
            source_provenance=(),
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
        filing_instance_evidence=None,
        source_provenance=(),
    )
    id_reversed = derive_calculation_revision_id(
        work_unit_id="c" * 64,
        input_values_by_casilla_id={_INPUT_CASILLA_002: "2.00", _INPUT_CASILLA_001: "1.00"},
        binding_overrides={},
        casilla_values={
            _ORDERED_OUTPUT_CASILLA_020: Decimal("6.00"),
            _ORDERED_OUTPUT_CASILLA_010: Decimal("5.00"),
        },
        filing_instance_evidence=None,
        source_provenance=(),
    )
    assert id_ordered == id_reversed


def test_revision_id_includes_present_borrador_metadata() -> None:
    """Adding borrador metadata to otherwise-identical inputs must change the id."""
    base = derive_calculation_revision_id(
        work_unit_id="b" * 64,
        input_values_by_casilla_id={_INPUT_CASILLA_001: "10.00"},
        binding_overrides={},
        casilla_values={_OUTPUT_CASILLA_002: Decimal("15.00")},
        filing_instance_evidence=None,
        source_provenance=(),
    )
    with_borrador = derive_calculation_revision_id(
        work_unit_id="b" * 64,
        input_values_by_casilla_id={_INPUT_CASILLA_001: "10.00"},
        binding_overrides={},
        casilla_values={_OUTPUT_CASILLA_002: Decimal("15.00")},
        borrador_snapshot_id="snapshot-100-2025",
        bindings_sourced_from_borrador=("casilla_001",),
        filing_instance_evidence=None,
        source_provenance=(),
    )

    assert with_borrador != base


def test_detail_rows_sort_key_handles_all_four_row_types() -> None:
    """Regression: sort key must work for all four row types (M184/M232 use nif,
    M349 uses nif_comunitario, M347 uses nif). This test verifies the sort key
    accessor correctly extracts the identifier field for each row type."""
    from ..row_models import (
        Modelo184MemberRow,
        Modelo232VinculadaRow,
        Modelo347ContraparteRow,
        Modelo349OperadorRow,
    )

    # Create one row of each type with distinct nif/nif_comunitario values.
    m184_row = Modelo184MemberRow(nif="12345678A", porcentaje=Decimal("50.00"), importe=Decimal("100.00"), clave="D")
    m232_row = Modelo232VinculadaRow(pais="ES", nif="87654321B", importe=Decimal("200.00"))
    m349_row = Modelo349OperadorRow(
        codigo_pais="DE",
        nif_comunitario="DE123456789",
        razon_social="Deutschland GmbH",
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
        filing_instance_evidence=None,
        source_provenance=(),
    )
    # Same rows in reverse order must produce the same id (sort-insensitive).
    id2 = derive_calculation_revision_id(
        work_unit_id="a" * 64,
        input_values_by_casilla_id={},
        binding_overrides={},
        casilla_values={},
        detail_rows=(m347_row, m349_row, m232_row, m184_row),
        filing_instance_evidence=None,
        source_provenance=(),
    )
    assert id1 == id2, "Row sort key must handle all four row types consistently"
