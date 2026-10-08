"""Complete fixed-row membership preserves unknown and known-unused states."""

import pytest
from pydantic import ValidationError

from ....core.aggregation import BindingSourceKind
from ..record_row_membership import ClosedRecordRowSet, RecordRowMembership, validate_closed_record_row_sets
from ..registry.schema_references import RegistrySnapshotRef

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def _closed_rows(rows: tuple[RecordRowMembership, ...]) -> ClosedRecordRowSet:
    return ClosedRecordRowSet(
        record_id="services",
        bucket_id="fictional-profile",
        work_unit_id="a" * 64,
        registry_snapshot_ref=RegistrySnapshotRef(
            modelo="369", revision_id="esquema-exterior", modelo_year=2025, period="EXT-1T"
        ),
        authority_generation="b" * 64,
        source_kind=BindingSourceKind.LEDGER_OSS_AGGREGATION,
        source_ref="fictional-collection",
        source_fingerprint="c" * 64,
        rows=rows,
    )


def test_complete_empty_is_an_explicit_membership_claim() -> None:
    closed = _closed_rows((RecordRowMembership(row_index=1, binding_ids=("country", "quota"), occupied=False),))
    assert closed.unused_binding_ids == {"country", "quota"}
    validate_closed_record_row_sets((closed,), supplied_binding_ids=set())
    with pytest.raises(ValueError, match="unused record row"):
        validate_closed_record_row_sets((closed,), supplied_binding_ids={"quota"})
    # No carrier makes no assertion, including when no values were supplied.
    validate_closed_record_row_sets((), supplied_binding_ids=set())


def test_occupied_row_does_not_assert_required_values_are_available() -> None:
    closed = _closed_rows((RecordRowMembership(row_index=1, binding_ids=("country", "quota"), occupied=True),))
    assert closed.unused_binding_ids == frozenset()
    validate_closed_record_row_sets((closed,), supplied_binding_ids={"country"})


@pytest.mark.parametrize("indices", [(2,), (1, 1), (1, 3)])
def test_missing_or_repeated_coordinates_cannot_close_a_table(indices: tuple[int, ...]) -> None:
    with pytest.raises(ValidationError, match="every slot exactly once"):
        _closed_rows(
            tuple(
                RecordRowMembership(row_index=i, binding_ids=(f"binding-{offset}",), occupied=False)
                for offset, i in enumerate(indices)
            )
        )


def test_binding_cannot_belong_to_two_rows() -> None:
    with pytest.raises(ValidationError, match="multiple slots"):
        _closed_rows(
            tuple(RecordRowMembership(row_index=i, binding_ids=("same-binding",), occupied=False) for i in (1, 2))
        )


def test_membership_order_has_one_canonical_serialization() -> None:
    row1 = RecordRowMembership(row_index=1, binding_ids=("quota", "country"), occupied=True)
    row2 = RecordRowMembership(row_index=2, binding_ids=("quota-2", "country-2"), occupied=False)
    first = _closed_rows((row2, row1))
    second = _closed_rows((row1, row2))
    assert first.model_dump_json() == second.model_dump_json()
    assert first.rows[0].binding_ids == ("country", "quota")
    assert ClosedRecordRowSet.model_validate_json(first.model_dump_json()) == first


@pytest.mark.parametrize(
    "field,value", [("bucket_id", "other-profile"), ("work_unit_id", "d" * 64), ("authority_generation", "e" * 64)]
)
def test_one_resolution_cannot_mix_calculation_scopes(field: str, value: str) -> None:
    first = _closed_rows((RecordRowMembership(row_index=1, binding_ids=("first",), occupied=False),))
    second = ClosedRecordRowSet.model_validate(
        {
            **dict(first),
            "record_id": "corrections",
            "rows": (RecordRowMembership(row_index=1, binding_ids=("second",), occupied=False),),
            field: value,
        }
    )
    with pytest.raises(ValueError, match="different calculation scopes"):
        validate_closed_record_row_sets((first, second), supplied_binding_ids=set())


def test_repeated_record_owner_is_ambiguous_even_when_values_match() -> None:
    closed = _closed_rows((RecordRowMembership(row_index=1, binding_ids=("country",), occupied=False),))
    with pytest.raises(ValueError, match="ambiguous ownership"):
        validate_closed_record_row_sets((closed, closed), supplied_binding_ids=set())
