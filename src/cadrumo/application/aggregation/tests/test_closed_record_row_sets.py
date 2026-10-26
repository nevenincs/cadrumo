"""Membership evidence and source values travel atomically through both merges."""

from decimal import Decimal

import pytest
from pydantic import ValidationError

from ....core.aggregation import BindingSourceKind
from ....domain.calculations.record_row_membership import ClosedRecordRowSet, RecordRowMembership
from ....domain.calculations.registry.schema_references import RegistrySnapshotRef
from ..errors import AggregationValidationError
from ..source_mesh import CalculationSourceDiagnostic, CalculationSourceResolution
from ..source_resolution_operations import merge_source_resolutions, merge_source_resolutions_by_precedence

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def _collection() -> ClosedRecordRowSet:
    return ClosedRecordRowSet(
        record_id="services",
        bucket_id="fictional-profile",
        work_unit_id="a" * 64,
        registry_snapshot_ref=RegistrySnapshotRef(
            modelo="369", revision_id="esquema-exterior", modelo_year=2025, period="EXT-1T"
        ),
        authority_generation="b" * 64,
        source_kind=BindingSourceKind.LEDGER_OSS_AGGREGATION,
        source_ref="sensitive-collection-reference",
        source_fingerprint="c" * 64,
        rows=(
            RecordRowMembership(row_index=1, binding_ids=("country-1", "quota-1"), occupied=True),
            RecordRowMembership(row_index=2, binding_ids=("country-2", "quota-2"), occupied=False),
        ),
    )


def _resolution() -> CalculationSourceResolution:
    return CalculationSourceResolution(
        resolver_id="oss",
        owned_sources=(BindingSourceKind.LEDGER_OSS_AGGREGATION,),
        binding_values={"quota-1": Decimal("190")},
        enum_binding_values={"country-1": "DE"},
        closed_record_row_sets=(_collection(),),
    )


@pytest.mark.parametrize("merge", [merge_source_resolutions, merge_source_resolutions_by_precedence])
def test_unrelated_source_preserves_private_membership_and_values(merge) -> None:
    original = _resolution()
    result = merge(
        (original, CalculationSourceResolution(resolver_id="other", binding_values={"unrelated": Decimal("20")}))
    )
    assert result.closed_record_row_sets == original.closed_record_row_sets
    assert result.binding_values["quota-1"] == Decimal("190")
    assert result.enum_binding_values["country-1"] == "DE"
    assert "closed_record_row_sets" not in result.model_dump(mode="json")
    assert "sensitive-collection-reference" not in result.model_dump_json()
    assert "sensitive-collection-reference" not in repr(result)


@pytest.mark.parametrize("merge", [merge_source_resolutions, merge_source_resolutions_by_precedence])
@pytest.mark.parametrize("binding", ["quota-1", "quota-2"])
@pytest.mark.parametrize("reverse", [False, True])
def test_overlay_cannot_change_a_closed_table_in_either_order(merge, binding: str, reverse: bool) -> None:
    sources = (_resolution(), CalculationSourceResolution(resolver_id="caller", binding_values={binding: Decimal("0")}))
    with pytest.raises(AggregationValidationError):
        merge(tuple(reversed(sources)) if reverse else sources)


@pytest.mark.parametrize("merge", [merge_source_resolutions, merge_source_resolutions_by_precedence])
def test_two_owners_cannot_supply_the_same_membership(merge) -> None:
    with pytest.raises(AggregationValidationError):
        merge((_resolution(), _resolution()))


@pytest.mark.parametrize(
    "channel,value",
    [("binding_values", Decimal("0")), ("enum_binding_values", "DE"), ("boolean_binding_values", False)],
)
def test_unused_row_rejects_every_populated_scalar_channel(channel: str, value) -> None:
    with pytest.raises(ValidationError):
        CalculationSourceResolution.model_validate({**dict(_resolution()), channel: {"quota-2": value}})


@pytest.mark.parametrize("reason", ["storage_degraded", "unrouted_observation"])
def test_degraded_or_unrouted_source_cannot_close_its_table(reason) -> None:
    with pytest.raises(ValidationError):
        CalculationSourceResolution.model_validate(
            {
                **dict(_resolution()),
                "diagnostics": (
                    CalculationSourceDiagnostic(
                        reason=reason,
                        source_kind="ledger_oss_aggregation",
                        resolver_id="oss",
                        message="Incomplete source",
                    ),
                ),
            }
        )


def test_collection_source_requires_declared_ownership() -> None:
    with pytest.raises(ValidationError):
        CalculationSourceResolution.model_validate({**dict(_resolution()), "owned_sources": ()})
