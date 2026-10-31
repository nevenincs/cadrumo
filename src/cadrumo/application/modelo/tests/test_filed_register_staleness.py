"""A sealed revision goes stale against the asset register as a state of the read, never by changing."""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from typing import cast

import pytest

from ....core.period import Period
from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ....domain.calculations.registry.tests.published_authority import published_snapshot
from ....domain.modelos.calculation_revision import (
    CalculationRevision,
    CalculationRevisionState,
    derive_calculation_revision_id,
)
from ....domain.modelos.codes import ModeloCode
from ....domain.modelos.ledger_filing_snapshot import FiledRegisterState
from ....domain.modelos.work_unit import WorkUnit, WorkUnitCatalogue, derive_work_unit_id
from ....domain.transactions.models import TransactionCatalogue
from ...actividad_asset.history import ActivityAssetHistory
from ...aggregation.ledger_filing_snapshot import stale_filed_revisions
from ...aggregation.ledger_membership import LedgerMembershipPorts
from ...aggregation.tests.test_modelo_bindings_asset_disposal import disposed_asset_history
from ...aggregation.tests.test_modelo_source_mesh_ledger import (
    InMemoryTransactionCatalogueRepository,
    activity_asset_ledger_membership,
    machine_asset,
    machine_claim,
    resolve_m100,
)
from ...ledger.stale_filing_query import read_stale_ledger_filings
from ..calculation_bucket_actions import _source_provenance_refs
from ..filed_register_reader import filed_register_reader

pytestmark = [pytest.mark.unit, pytest.mark.hex_application, pytest.mark.usefixtures("operation")]

_BUCKET_ID = "28282828-2828-4828-8828-282828282828"
_OTHER_BUCKET_ID = "39393939-3939-4939-8939-393939393939"
_AT = datetime(2026, 4, 20, 12, 0, tzinfo=UTC)


def _work_unit(revision_id: str, *, bucket_id: str = _BUCKET_ID) -> WorkUnit:
    period = Period.from_year_and_code(2025, "0A")
    return WorkUnit(
        work_unit_id=derive_work_unit_id(
            bucket_id=bucket_id,
            modelo="100",
            filing_year=2025,
            period=period,
            revision_id=revision_id,
        ),
        bucket_id=bucket_id,
        modelo=ModeloCode("100"),
        filing_year=2025,
        period=period,
        revision_id=revision_id,
        name="100-2025-0A",
        created_at=_AT,
        updated_at=_AT,
    )


def _filed(history: ActivityAssetHistory, *, state: CalculationRevisionState) -> tuple[WorkUnit, CalculationRevision]:
    """Calculate through the real resolver and seal what its provenance says."""
    snapshot = published_snapshot("100", filing_year=2025, period="0A")
    work_unit = _work_unit(snapshot.revision.id)
    provenance = _source_provenance_refs(resolve_m100(history))
    revision = CalculationRevision(
        calculation_revision_id=derive_calculation_revision_id(
            work_unit_id=work_unit.work_unit_id,
            input_values_by_casilla_id={},
            binding_overrides={},
            casilla_values={},
            filing_instance_evidence=None,
            source_provenance=provenance,
        ),
        work_unit_id=work_unit.work_unit_id,
        registry_snapshot_ref=snapshot.snapshot_ref,
        state=CalculationRevisionState.BORRADOR,
        input_values_by_casilla_id={},
        binding_overrides={},
        casilla_values={},
        observations=(),
        created_at=_AT,
        updated_at=_AT,
        filing_instance_evidence=None,
        source_provenance=provenance,
    )
    return work_unit, revision.model_copy(update={"state": state})


def _stale(work_unit: WorkUnit, revision: CalculationRevision, register: ActivityAssetHistory):
    membership = activity_asset_ledger_membership(
        work_unit,
        register,
        InMemoryTransactionCatalogueRepository(bucket_id=_BUCKET_ID),
        modelo="100",
        period_code="0A",
    )
    return stale_filed_revisions(
        revisions={revision.calculation_revision_id: revision},
        catalogue=TransactionCatalogue(),
        register_reader=lambda _revision: membership.activity_asset_consumption,
    )


def test_a_claim_recorded_after_filing_makes_the_filed_revision_stale_without_touching_it() -> None:
    asset = machine_asset("a" * 64)
    work_unit, filed = _filed(ActivityAssetHistory(revisions=(asset,)), state=CalculationRevisionState.PRESENTADO)
    before = filed.model_dump()

    ((found, verdict),) = _stale(
        work_unit, filed, ActivityAssetHistory(revisions=(asset,), claims=(machine_claim(asset),))
    )

    assert found is filed
    assert filed.model_dump() == before
    assert verdict.is_stale is True
    assert verdict.register_state is FiledRegisterState.CHANGED
    assert verdict.register_change_count == 1
    assert (verdict.changed, verdict.removed) == ((), ())


def test_superseding_a_consumed_claim_after_filing_counts_both_sides() -> None:
    asset = machine_asset("a" * 64)
    original = machine_claim(asset)
    replacement = original.model_copy(update={"amount": Decimal("100.00"), "supersedes_claim_id": original.claim_id})
    work_unit, filed = _filed(
        ActivityAssetHistory(revisions=(asset,), claims=(original,)), state=CalculationRevisionState.PRESENTADO
    )

    ((_, verdict),) = _stale(work_unit, filed, ActivityAssetHistory(revisions=(asset,), claims=(original, replacement)))

    assert verdict.register_state is FiledRegisterState.CHANGED
    assert verdict.register_change_count == 2


def test_an_unchanged_register_leaves_the_filed_revision_current() -> None:
    asset = machine_asset("a" * 64)
    history = ActivityAssetHistory(revisions=(asset,), claims=(machine_claim(asset),))
    work_unit, filed = _filed(history, state=CalculationRevisionState.PRESENTADO)

    assert _stale(work_unit, filed, history) == ()


def test_a_draft_stays_with_the_verify_gate_and_is_not_reported_here() -> None:
    asset = machine_asset("a" * 64)
    work_unit, draft = _filed(ActivityAssetHistory(revisions=(asset,)), state=CalculationRevisionState.BORRADOR)

    assert _stale(work_unit, draft, ActivityAssetHistory(revisions=(asset,), claims=(machine_claim(asset),))) == ()


def test_an_unreadable_register_is_reported_as_unavailable_and_not_as_drift() -> None:
    asset = machine_asset("a" * 64)
    _, filed = _filed(ActivityAssetHistory(revisions=(asset,)), state=CalculationRevisionState.PRESENTADO)

    ((_, verdict),) = stale_filed_revisions(
        revisions={filed.calculation_revision_id: filed},
        catalogue=TransactionCatalogue(),
        register_reader=lambda _revision: None,
    )

    assert verdict.is_stale is False
    assert verdict.register_state is FiledRegisterState.UNAVAILABLE
    assert verdict.register_change_count == 0


def test_the_status_query_carries_the_state_and_keeps_other_profiles_out() -> None:
    asset = machine_asset("a" * 64)
    claim = machine_claim(asset)
    work_unit, filed = _filed(ActivityAssetHistory(revisions=(asset,)), state=CalculationRevisionState.PRESENTADO)
    claimed = filed.activity_asset_consumption.model_copy(update={"claim_ids": (claim.claim_id,)})

    def read(bucket_id: str):
        return read_stale_ledger_filings(
            bucket_id=bucket_id,
            revisions={filed.calculation_revision_id: filed},
            work_units=WorkUnitCatalogue(work_units={work_unit.work_unit_id: work_unit}),
            transactions=TransactionCatalogue(),
            register_reader=lambda _revision: claimed,
        )

    (finding,) = read(_BUCKET_ID)

    assert finding.register_state is FiledRegisterState.CHANGED
    assert finding.register_change_count == 1
    assert (finding.changed_count, finding.removed_count) == (0, 0)
    assert read(_OTHER_BUCKET_ID) == ()


def test_the_reader_answers_what_was_recorded_outside_this_profile_and_none_for_an_unknown_revision(
    operation: PinnedAuthorityOperation,
) -> None:
    asset = machine_asset("a" * 64)
    work_unit, filed = _filed(
        ActivityAssetHistory(revisions=(asset,), claims=(machine_claim(asset),)),
        state=CalculationRevisionState.PRESENTADO,
    )
    unknown = _work_unit("no-such-revision")
    ports = cast("LedgerMembershipPorts", object())

    def read(unit: WorkUnit, *, bucket_id: str) -> object:
        catalogue = WorkUnitCatalogue(work_units={unit.work_unit_id: unit})
        target = filed.model_copy(update={"work_unit_id": unit.work_unit_id})
        return filed_register_reader(bucket_id=bucket_id, work_units=catalogue, ports=ports, operation=operation)(
            target
        )

    assert read(work_unit, bucket_id=_OTHER_BUCKET_ID) == filed.activity_asset_consumption
    assert read(unknown, bucket_id=_BUCKET_ID) is None


def test_a_claim_of_an_earlier_year_that_moves_a_filed_baja_makes_it_stale() -> None:
    """The 2025 gain goes from 897.53 to 1,200.00 with no 2025 claim and no new baja revision."""
    unclaimed = disposed_asset_history(in_service=date(2024, 1, 1))
    claimed = disposed_asset_history(in_service=date(2024, 1, 1), prior_claim="1200.00")
    work_unit, filed = _filed(unclaimed, state=CalculationRevisionState.PRESENTADO)

    ((found, verdict),) = _stale(work_unit, filed, claimed)

    assert found is filed
    assert verdict.register_state is FiledRegisterState.CHANGED
    assert verdict.register_change_count == 1
    assert _stale(work_unit, filed, unclaimed) == ()
