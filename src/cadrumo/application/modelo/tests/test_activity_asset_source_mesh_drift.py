"""Real resolver provenance stays current only while its consumed register stays current."""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal

import pytest

from ....core.period import Period
from ....domain.calculations.registry.tests.published_authority import published_snapshot
from ....domain.modelos.calculation_revision import (
    CalculationRevision,
    CalculationRevisionState,
    derive_calculation_revision_id,
)
from ....domain.modelos.codes import ModeloCode
from ....domain.modelos.ledger_filing_snapshot import FiledRegisterState
from ....domain.modelos.verification_report import ModeloVerificationFinding
from ....domain.modelos.work_unit import WorkUnit, WorkUnitCatalogue, derive_work_unit_id
from ....domain.renta.actividad_asset.claims import AmortizationClaim
from ....domain.renta.actividad_asset.disposal import ActivityAssetDisposal, ActivityAssetDisposalReason
from ....domain.renta.actividad_asset.election import (
    ActivityAssetAmortizationElection,
    AmortizationMethod,
    DirectEstimationRegime,
)
from ....domain.renta.actividad_asset.lifecycle import ActivityAssetRevision
from ....domain.transactions.models import TransactionCatalogue
from ...actividad_asset.history import ActivityAssetHistory
from ...aggregation.ledger_filing_snapshot import stale_filed_revisions
from ...aggregation.tests.test_modelo_source_mesh_ledger import (
    InMemoryTransactionCatalogueRepository,
    _m130_box,
    activity_asset_ledger_membership,
    machine_asset,
    machine_claim,
    register_asset,
    resolve_m100,
    resolve_m130,
)
from .._ledger_drift_gate import ledger_drift_findings
from ..activity_asset_claim_consumers import calculation_revisions_consuming_claim
from ..calculation_bucket_actions import _source_provenance_refs

pytestmark = [pytest.mark.unit, pytest.mark.hex_application, pytest.mark.usefixtures("operation")]

_BUCKET_ID = "28282828-2828-4828-8828-282828282828"

_DRIFT_AT = datetime(2026, 4, 20, 12, 0, tzinfo=UTC)
_ASSET_DRIFT_KEY = "application.modelo.findings.activity_asset_register_drift"


def _drift_work_unit(modelo: str, period_code: str, revision_id: str) -> WorkUnit:
    period = Period.from_year_and_code(2025, period_code)
    return WorkUnit(
        work_unit_id=derive_work_unit_id(
            bucket_id=_BUCKET_ID,
            modelo=modelo,
            filing_year=2025,
            period=period,
            revision_id=revision_id,
        ),
        bucket_id=_BUCKET_ID,
        modelo=ModeloCode(modelo),
        filing_year=2025,
        period=period,
        revision_id=revision_id,
        name=f"{modelo}-2025-{period_code}",
        created_at=_DRIFT_AT,
        updated_at=_DRIFT_AT,
    )


def _calculated_draft(
    history: ActivityAssetHistory,
    *,
    modelo: str,
    period_code: str,
) -> tuple[WorkUnit, CalculationRevision]:
    """Calculate through the real resolver and persist what its provenance says."""
    resolution = resolve_m100(history) if modelo == "100" else resolve_m130(history, period_code)
    snapshot = published_snapshot(modelo, filing_year=2025, period=period_code)
    work_unit = _drift_work_unit(modelo, period_code, snapshot.revision.id)
    provenance = _source_provenance_refs(resolution)
    revision_id = derive_calculation_revision_id(
        work_unit_id=work_unit.work_unit_id,
        input_values_by_casilla_id={},
        binding_overrides={},
        casilla_values={},
        filing_instance_evidence=None,
        source_provenance=provenance,
    )
    return work_unit, CalculationRevision(
        calculation_revision_id=revision_id,
        work_unit_id=work_unit.work_unit_id,
        registry_snapshot_ref=snapshot.snapshot_ref,
        state=CalculationRevisionState.BORRADOR,
        input_values_by_casilla_id={},
        binding_overrides={},
        casilla_values={},
        observations=(),
        created_at=_DRIFT_AT,
        updated_at=_DRIFT_AT,
        filing_instance_evidence=None,
        source_provenance=provenance,
    )


def _asset_drift(
    draft: tuple[WorkUnit, CalculationRevision],
    history: ActivityAssetHistory,
    *,
    modelo: str,
    period_code: str,
) -> list[ModeloVerificationFinding]:
    """Run the verify-time gate against the register as it stands in ``history``."""
    work_unit, revision = draft
    tx_repo = InMemoryTransactionCatalogueRepository(bucket_id=_BUCKET_ID)
    membership = activity_asset_ledger_membership(work_unit, history, tx_repo, modelo=modelo, period_code=period_code)
    return ledger_drift_findings(
        target=revision,
        work_unit=work_unit,
        transaction_repository=tx_repo,
        current_membership=membership,
    )


def _asset_facts(findings: list[ModeloVerificationFinding]) -> dict[str, object]:
    (finding,) = findings
    assert finding.message_locale_key == _ASSET_DRIFT_KEY
    return dict(finding.message_facts)


def test_a_claim_recorded_after_the_year_was_calculated_makes_it_stale() -> None:
    """The draft rested on no claim; the register now yields one, so the figure is out of date."""
    asset = machine_asset("a" * 64)
    before = ActivityAssetHistory(revisions=(asset,))
    after = ActivityAssetHistory(revisions=(asset,), claims=(machine_claim(asset),))
    draft = _calculated_draft(before, modelo="100", period_code="0A")
    assert draft[1].activity_asset_consumption.claim_ids == ()

    facts = _asset_facts(_asset_drift(draft, after, modelo="100", period_code="0A"))

    assert (facts["claims_added"], facts["claims_removed"], facts["schedules_changed"]) == (1, 0, 0)


def test_an_identical_register_read_leaves_the_calculated_year_current() -> None:
    asset = machine_asset("a" * 64)
    history = ActivityAssetHistory(revisions=(asset,), claims=(machine_claim(asset),))
    draft = _calculated_draft(history, modelo="100", period_code="0A")
    assert draft[1].activity_asset_consumption.claim_ids == (machine_claim(asset).claim_id,)

    assert _asset_drift(draft, history, modelo="100", period_code="0A") == []


def test_superseding_a_consumed_claim_makes_the_year_stale() -> None:
    asset = machine_asset("a" * 64)
    original = machine_claim(asset)
    replacement = original.model_copy(update={"amount": Decimal("100.00"), "supersedes_claim_id": original.claim_id})
    draft = _calculated_draft(
        ActivityAssetHistory(revisions=(asset,), claims=(original,)), modelo="100", period_code="0A"
    )

    facts = _asset_facts(
        _asset_drift(
            draft,
            ActivityAssetHistory(revisions=(asset,), claims=(original, replacement)),
            modelo="100",
            period_code="0A",
        ),
    )

    assert (facts["claims_added"], facts["claims_removed"]) == (1, 1)


def test_modelo_130_goes_stale_when_the_schedule_fingerprint_it_consumed_changes() -> None:
    original = register_asset("furniture", transaction_id="c" * 64)
    moved = register_asset("furniture", transaction_id="c" * 64, in_service=date(2025, 1, 15))
    draft = _calculated_draft(ActivityAssetHistory(revisions=(original,)), modelo="130", period_code="1T")
    (recorded,) = draft[1].activity_asset_consumption.schedule_fingerprints

    assert _asset_drift(draft, ActivityAssetHistory(revisions=(original,)), modelo="130", period_code="1T") == []
    facts = _asset_facts(_asset_drift(draft, ActivityAssetHistory(revisions=(moved,)), modelo="130", period_code="1T"))

    assert facts["schedules_changed"] == 1
    reread = _calculated_draft(ActivityAssetHistory(revisions=(moved,)), modelo="130", period_code="1T")
    assert recorded not in reread[1].activity_asset_consumption.schedule_fingerprints


def test_the_consumers_of_a_claim_are_this_buckets_revisions_that_recorded_it() -> None:
    asset = machine_asset("a" * 64)
    claim = machine_claim(asset)
    consuming_unit, consuming = _calculated_draft(
        ActivityAssetHistory(revisions=(asset,), claims=(claim,)), modelo="100", period_code="0A"
    )
    _, unrelated = _calculated_draft(ActivityAssetHistory(revisions=(asset,)), modelo="100", period_code="0A")
    catalogue = WorkUnitCatalogue(work_units={consuming_unit.work_unit_id: consuming_unit})

    found = calculation_revisions_consuming_claim(
        claim.claim_id, bucket_id=_BUCKET_ID, revisions=(unrelated, consuming), work_units=catalogue
    )
    other_bucket = calculation_revisions_consuming_claim(
        claim.claim_id, bucket_id="39393939-3939-4939-8939-393939393939", revisions=(consuming,), work_units=catalogue
    )

    assert [revision.calculation_revision_id for revision in found] == [consuming.calculation_revision_id]
    assert other_bucket == ()


def _prior_year_claim(asset: ActivityAssetRevision, amount: str) -> AmortizationClaim:
    return AmortizationClaim(
        asset_id=asset.asset_id,
        asset_revision_id=asset.revision_id,
        asset_kind=asset.asset_kind,
        tax_year=2024,
        covered_from=date(2024, 1, 1),
        covered_until=date(2025, 1, 1),
        amount=Decimal(amount),
        schedule_fingerprint="7" * 64,
        authority_generation="published-test-generation",
        source_reference="test table",
        creating_operation="record-amortization",
    )


def _filed_stale(
    draft: tuple[WorkUnit, CalculationRevision],
    history: ActivityAssetHistory,
    *,
    period_code: str,
):
    """Read the sealed revision through the filed-state detector, against the register as it stands."""
    work_unit, revision = draft
    membership = activity_asset_ledger_membership(
        work_unit,
        history,
        InMemoryTransactionCatalogueRepository(bucket_id=_BUCKET_ID),
        modelo="130",
        period_code=period_code,
    )
    sealed = revision.model_copy(update={"state": CalculationRevisionState.PRESENTADO})
    return stale_filed_revisions(
        revisions={sealed.calculation_revision_id: sealed},
        catalogue=TransactionCatalogue(),
        register_reader=lambda _revision: membership.activity_asset_consumption,
    )


def _constant_asset() -> ActivityAssetRevision:
    """12,000.00 from 1 January 2024 at the maquinaria maximum of 12%, weighted 2.5 for its 8.33-year period: 30%."""
    return register_asset(
        "press",
        transaction_id="c" * 64,
        in_service=date(2024, 1, 1),
        election=ActivityAssetAmortizationElection(
            regime=DirectEstimationRegime.NORMAL,
            method=AmortizationMethod.CONSTANT_PERCENTAGE,
            authority_class_key="maquinaria",
        ),
    )


def test_a_prior_year_claim_that_moves_a_constant_percentage_box_makes_the_modelo_130_stale() -> None:
    asset = _constant_asset()
    before = ActivityAssetHistory(revisions=(asset,))
    after = ActivityAssetHistory(revisions=(asset,), claims=(_prior_year_claim(asset, "3000.00"),))
    draft = _calculated_draft(before, modelo="130", period_code="4T")

    # 30% of the 12,000.00 pending, then of the 9,000.00 left by the 2024 claim.
    assert _m130_box(resolve_m130(before, "4T")) == Decimal("3600.00")
    assert _m130_box(resolve_m130(after, "4T")) == Decimal("2700.00")
    facts = _asset_facts(_asset_drift(draft, after, modelo="130", period_code="4T"))

    assert facts["schedules_changed"] == 1
    assert (facts["claims_added"], facts["claims_removed"]) == (0, 0)
    ((_, verdict),) = _filed_stale(draft, after, period_code="4T")
    assert verdict.register_state is FiledRegisterState.CHANGED
    assert verdict.register_change_count == 2


def test_a_prior_year_claim_leaves_a_linear_modelo_130_current_while_its_figure_holds() -> None:
    asset = register_asset("furniture", transaction_id="c" * 64, in_service=date(2024, 1, 1))
    before = ActivityAssetHistory(revisions=(asset,))
    # 12,000.00 at 10% charges 1,200.00 a year, and 3,000.00 claimed in 2024 leaves that figure whole.
    after = ActivityAssetHistory(revisions=(asset,), claims=(_prior_year_claim(asset, "3000.00"),))
    draft = _calculated_draft(before, modelo="130", period_code="4T")

    assert _asset_drift(draft, after, modelo="130", period_code="4T") == []
    assert _filed_stale(draft, after, period_code="4T") == ()


def test_a_prior_year_claim_that_caps_a_linear_modelo_130_makes_it_stale() -> None:
    asset = register_asset("furniture", transaction_id="c" * 64, in_service=date(2024, 1, 1))
    before = ActivityAssetHistory(revisions=(asset,))
    # Only 1,000.00 of the 12,000.00 remains, below the 1,200.00 a year charges.
    after = ActivityAssetHistory(revisions=(asset,), claims=(_prior_year_claim(asset, "11000.00"),))
    draft = _calculated_draft(before, modelo="130", period_code="4T")

    facts = _asset_facts(_asset_drift(draft, after, modelo="130", period_code="4T"))

    assert facts["schedules_changed"] == 1
    assert _filed_stale(draft, after, period_code="4T")


def _sale_on(day: date) -> ActivityAssetDisposal:
    return ActivityAssetDisposal(
        disposal_date=day,
        reason=ActivityAssetDisposalReason.SALE,
        proceeds=Decimal("100.00"),
        transmission_costs=Decimal("0.00"),
    )


def test_a_later_baja_with_the_same_figure_leaves_the_modelo_130_current() -> None:
    asset = register_asset("furniture", transaction_id="c" * 64)
    draft = _calculated_draft(ActivityAssetHistory(revisions=(asset,)), modelo="130", period_code="1T")
    disposed = ActivityAssetHistory(revisions=(asset, asset.with_disposal(_sale_on(date(2026, 6, 30)))))

    assert _asset_drift(draft, disposed, modelo="130", period_code="1T") == []
    assert _filed_stale(draft, disposed, period_code="1T") == ()


def test_a_baja_inside_the_period_moves_the_figure_and_makes_the_modelo_130_stale() -> None:
    asset = register_asset("furniture", transaction_id="c" * 64)
    draft = _calculated_draft(ActivityAssetHistory(revisions=(asset,)), modelo="130", period_code="1T")
    disposed = ActivityAssetHistory(revisions=(asset, asset.with_disposal(_sale_on(date(2025, 2, 15)))))

    facts = _asset_facts(_asset_drift(draft, disposed, modelo="130", period_code="1T"))

    assert facts["schedules_changed"] == 1
    assert facts["disposals_changed"] == 1
    assert _filed_stale(draft, disposed, period_code="1T")
