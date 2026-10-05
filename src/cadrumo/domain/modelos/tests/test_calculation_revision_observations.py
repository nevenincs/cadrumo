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
    from ...calculations.registry.schema_references import RegistrySnapshotRef
    from ..calculation_revision import CalculationRevision, CalculationRevisionState

    work_unit_id = "d" * 64
    registry_snapshot_ref = RegistrySnapshotRef(
        modelo="303",
        revision_id="2026-y-siguientes",
        modelo_year=2026,
        period="1T",
    )
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
        registry_snapshot_ref=registry_snapshot_ref,
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
    from ...calculations.registry.schema_references import RegistrySnapshotRef
    from ..calculation_revision import CalculationRevision, CalculationRevisionState

    work_unit_id = "e" * 64
    registry_snapshot_ref = RegistrySnapshotRef(
        modelo="303",
        revision_id="2026-y-siguientes",
        modelo_year=2026,
        period="1T",
    )
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
            registry_snapshot_ref=registry_snapshot_ref,
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

    from ...calculations.registry.schema_references import RegistrySnapshotRef
    from ..calculation_revision import CalculationRevision, CalculationRevisionState

    work_unit_id = "f" * 64
    registry_snapshot_ref = RegistrySnapshotRef(
        modelo="303",
        revision_id="2026-y-siguientes",
        modelo_year=2026,
        period="1T",
    )
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
            registry_snapshot_ref=registry_snapshot_ref,
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
