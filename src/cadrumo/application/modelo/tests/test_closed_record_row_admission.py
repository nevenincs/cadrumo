"""Caller channels cannot detach fixed record rows from their source evidence."""

from decimal import Decimal
from typing import cast

import pytest

from ....core.aggregation import BindingSourceKind
from ....domain.calculations.record_row_membership import ClosedRecordRowSet, RecordRowMembership
from ....domain.calculations.registry.manual_input_selector import ManualInputProvider
from ....domain.calculations.registry.schema_references import RegistrySnapshotRef
from ....domain.calculations.registry.tests.published_authority import published_snapshot
from ....domain.modelos.work_unit import WorkUnit
from ....domain.transactions.protocols import TransactionCatalogueRepositoryProtocol
from ...aggregation.source_mesh import CalculationSourceResolution
from .. import calculation_actions
from ..action_errors import ModeloAggregationBindingError
from ..calculation_action_ports import CalculationActionPorts
from ..work_profile import ModeloWorkProfile

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


@pytest.mark.parametrize("occupied", [True, False])
@pytest.mark.parametrize("channel,value", [("enum", "DE"), ("enum", "FR"), ("numeric", Decimal("0"))])
def test_bucket_admission_refuses_caller_changes_to_closed_manual_slots(
    monkeypatch: pytest.MonkeyPatch, occupied: bool, channel: str, value: str | Decimal
) -> None:
    """Exercise final mesh admission, not just the lower-level merge helper.

    The producer is supplied at the mesh seam because this contract has no live
    producer yet. Registry ownership, source envelope and caller admission are
    real; the binding deliberately declares manual_input, not the mesh source.
    """
    snapshot = published_snapshot("369", filing_year=2025, period="EXT-1T")
    country = next(
        binding
        for binding in snapshot.revision.bindings
        if isinstance(binding.provider, ManualInputProvider)
        and binding.provider.record == "modelo-369-exterior-t36901"
        and binding.provider.field == "3-prestaciones-de-servicios-codigo-de-pais-em-de-consumo-1"
    )
    closed = ClosedRecordRowSet(
        record_id="modelo-369-exterior-t36901",
        bucket_id="fictional-profile",
        work_unit_id="a" * 64,
        registry_snapshot_ref=RegistrySnapshotRef(
            modelo="369", revision_id="esquema-exterior", modelo_year=2025, period="EXT-1T"
        ),
        authority_generation="b" * 64,
        source_kind=BindingSourceKind.LEDGER_OSS_AGGREGATION,
        source_ref="fictional-source-collection",
        source_fingerprint="c" * 64,
        rows=(RecordRowMembership(row_index=1, binding_ids=(country.id,), occupied=occupied),),
    )
    resolution = CalculationSourceResolution(
        resolver_id="ledger_oss_aggregation",
        owned_sources=(BindingSourceKind.LEDGER_OSS_AGGREGATION,),
        enum_binding_values={country.id: "DE"} if occupied else {},
        closed_record_row_sets=(closed,),
    )
    monkeypatch.setattr(calculation_actions, "resolve_bucket_source_mesh", lambda *args, **kwargs: resolution)
    numeric_values = {country.id: value} if isinstance(value, Decimal) else {}
    enum_values = {country.id: value} if isinstance(value, str) else {}
    # These opaque dependencies only pass to the replaced producer. Any attempt
    # by admission to read or mutate persistence through them fails the test.
    preparation = calculation_actions._BucketAggregationPreparation(
        snapshot=snapshot,
        binding_values=numeric_values,
        casilla_inputs={},
        work_unit=cast(WorkUnit, object()),
        profile=cast(ModeloWorkProfile, object()),
        source_casilla_inputs=None,
        m210_gross_income_source_mode=None,
        source_binding_values=None,
        relation_values={},
        source_relation_values=None,
    )
    with pytest.raises(ModeloAggregationBindingError) as raised:
        calculation_actions._resolve_bucket_aggregation_source_resolution(
            preparation=preparation,
            ports=cast(CalculationActionPorts, object()),
            foreign_asset_observations=(),
            foreign_asset_row_observations=(),
            text_casilla_inputs=None,
            m210_official_tipo_renta_code=None,
            enum_binding_values=enum_values,
            filing_period_date=None,
            transaction_repository=cast(TransactionCatalogueRepositoryProtocol, object()),
        )
    assert raised.value.context == {"rejected_binding_ids": [country.id]}
    assert "fictional-source-collection" not in str(raised.value)


def test_unclaimed_manual_enum_remains_editable() -> None:
    revision = published_snapshot("369", filing_year=2025, period="EXT-1T").revision
    manual = next(binding for binding in revision.bindings if isinstance(binding.provider, ManualInputProvider))
    calculation_actions._reject_caller_overrides_of_source_bindings(
        revision=revision,
        owned_sources=frozenset({BindingSourceKind.LEDGER_OSS_AGGREGATION}),
        caller_binding_values={},
        caller_casilla_inputs={},
        caller_enum_binding_values={manual.id: "DE"},
    )
