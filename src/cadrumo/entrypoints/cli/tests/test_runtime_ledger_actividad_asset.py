"""Activity-asset CLI bridge carries typed requests and correlated results."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from types import SimpleNamespace
from typing import Any, cast
from uuid import UUID

import pytest
import typer
from pydantic import BaseModel

from ....application.actividad_asset.history import ActivityAssetHistory, ActivityAssetHistoryClaimResult
from ....application.actividad_asset.operation_dtos import (
    ActivityAssetFilingHandoffSnapshot,
    ActivityAssetHistoryClaimResultSnapshot,
    ActivityAssetHistorySnapshot,
    ActivityAssetRevisionSnapshot,
    ScheduledAmortizationChargeSnapshot,
)
from ....application.actividad_asset.operations import ActivityAssetFilingHandoff
from ....application.actividad_asset.registered_operations import (
    ACTIVITY_ASSET_CLAIM_OPERATION_DEFINITION_ID,
    ACTIVITY_ASSET_CORRECT_OPERATION_DEFINITION_ID,
    ACTIVITY_ASSET_CREATE_OPERATION_DEFINITION_ID,
    ACTIVITY_ASSET_FILING_HANDOFF_OPERATION_DEFINITION_ID,
    ACTIVITY_ASSET_FORECAST_OPERATION_DEFINITION_ID,
    ACTIVITY_ASSET_INSPECT_OPERATION_DEFINITION_ID,
    ActivityAssetAuthorityProvenance,
    ActivityAssetClaimProjection,
    ActivityAssetClaimRequest,
    ActivityAssetCorrectProjection,
    ActivityAssetCorrectRequest,
    ActivityAssetCreateProjection,
    ActivityAssetCreateRequest,
    ActivityAssetFilingHandoffProjection,
    ActivityAssetFilingHandoffRequest,
    ActivityAssetForecastProjection,
    ActivityAssetForecastRequest,
    ActivityAssetInspectionRevision,
    ActivityAssetInspectProjection,
    ActivityAssetInspectRequest,
)
from ....application.operations.public_scalar import PublicDecimal
from ....core.operations import OperationEffect, profile_operation_subject
from ....domain.renta.actividad_asset.claims import AmortizationClaim, ClaimProjection, asset_schedule_history
from ....domain.renta.actividad_asset.election import (
    AcquiredCondition,
    ActivityAssetAmortizationElection,
    AmortizationMethod,
    DirectEstimationRegime,
)
from ....domain.renta.actividad_asset.lifecycle import (
    AcquisitionLineageReference,
    AcquisitionShape,
    ActivityAssetBasis,
    ActivityAssetRevision,
    AssetBasisStage,
    AssetKind,
    OpeningAmortizationHistory,
    OpeningHistoryStatus,
)
from ....domain.renta.actividad_asset.schedule import ScheduleAuthority, ScheduledAmortizationCharge, schedule_charge
from .. import runtime_ledger_actividad_asset as bridge
from ..registered_operation_contracts import RegisteredOperationCompletion

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_PROFILE = UUID("5aa00000-0000-4000-8000-0000000000aa")
_OPERATION_ID = "a" * 64
_AUTHORITY = ActivityAssetAuthorityProvenance(logical_generation="b" * 64, reader_incarnation="c" * 64)


def _revision(*, number: int = 1, supersedes: str | None = None) -> ActivityAssetRevision:
    return ActivityAssetRevision(
        asset_id="bridge-asset",
        revision_number=number,
        supersedes_revision_id=supersedes,
        acquisition=AcquisitionLineageReference(
            observed_transaction_id="d" * 64,
            invoice_evidence_id="bridge-invoice",
            evidence_fingerprint="e" * 64,
        ),
        acquisition_shape=AcquisitionShape.PRIMARY_PURCHASE,
        asset_kind=AssetKind.MATERIAL,
        basis=ActivityAssetBasis(
            stage=AssetBasisStage.BUSINESS_ALLOCATED,
            basis_amount=Decimal("300.00"),
            prior_allocation_provenance="bridge allocation",
        ),
        in_service_date=date(2025, 1, 1),
        opening_history=OpeningAmortizationHistory(
            status=OpeningHistoryStatus.KNOWN,
            accumulated_amount=Decimal("0"),
        ),
        acquired_condition=AcquiredCondition.NEW,
        amortization=ActivityAssetAmortizationElection(
            regime=DirectEstimationRegime.NORMAL,
            method=AmortizationMethod.LINEAR,
            authority_class_key="equipo-proceso-informacion",
        ),
    )


def _schedule(revision: ActivityAssetRevision) -> ScheduledAmortizationCharge:
    return schedule_charge(
        revision,
        ScheduleAuthority(
            tax_year=2025,
            asset_kind=AssetKind.MATERIAL,
            method=AmortizationMethod.LINEAR,
            election_fingerprint=revision.amortization.fingerprint,
            annual_rate=Decimal("0.26"),
            authority_generation=_AUTHORITY.logical_generation,
            source_reference="bridge-pinned-source",
        ),
        covered_from=date(2025, 1, 1),
        covered_until=date(2026, 1, 1),
        history=asset_schedule_history((), (revision,), asset_id=revision.asset_id, tax_year=2025),
    )


def _context() -> typer.Context:
    return cast(typer.Context, cast(object, None))


def _bind(
    monkeypatch: pytest.MonkeyPatch,
    *,
    completion: RegisteredOperationCompletion[Any],
    definition_id: str,
    request_type: type[BaseModel],
) -> list[BaseModel]:
    requests: list[BaseModel] = []
    client = SimpleNamespace(profile_id=_PROFILE)
    monkeypatch.setattr(bridge, "active_bucket_id_or_refuse", lambda: str(_PROFILE))
    monkeypatch.setattr(bridge, "require_profile_client", lambda *_args, **_kwargs: client)

    def submit(_client: object, request: BaseModel, **kwargs: object) -> RegisteredOperationCompletion[Any]:
        requests.append(request)
        assert isinstance(request, request_type)
        assert kwargs["definition_id"] == definition_id
        assert kwargs["subject_ref"] == profile_operation_subject(str(_PROFILE))
        assert kwargs["result_type"] is type(completion.projection)
        assert kwargs["request_version"] == kwargs["result_version"] == 1
        assert kwargs["timeout"] == 120
        assert kwargs["allow_refusal_detail"] is True
        return completion

    monkeypatch.setattr(bridge, "run_registered_operation", submit)
    return requests


def test_create_bridge_sends_exact_profile_revision_and_correlates_history(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    revision = _revision()
    projection = ActivityAssetCreateProjection(
        profile_id=_PROFILE,
        authority=_AUTHORITY,
        outcome="succeeded",
        history=ActivityAssetHistorySnapshot.from_domain(ActivityAssetHistory(revisions=(revision,))),
    )
    completion = RegisteredOperationCompletion(
        operation_id=_OPERATION_ID,
        projection=projection,
        effect=OperationEffect.UPDATED,
    )
    requests = _bind(
        monkeypatch,
        completion=completion,
        definition_id=ACTIVITY_ASSET_CREATE_OPERATION_DEFINITION_ID,
        request_type=ActivityAssetCreateRequest,
    )

    assert bridge.create_activity_asset(_context(), revision=revision) is projection
    request = cast(ActivityAssetCreateRequest, requests[0])
    assert request.profile_id == _PROFILE
    assert request.revision.to_domain() == revision


def test_inspect_bridge_correlates_full_revision_identity_and_read_only_effect(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    revision = _revision()
    projection = ActivityAssetInspectProjection(
        profile_id=_PROFILE,
        authority=_AUTHORITY,
        outcome="succeeded",
        asset_id=revision.asset_id,
        revisions=(
            ActivityAssetInspectionRevision(
                revision=ActivityAssetRevisionSnapshot.from_domain(revision),
                revision_id=revision.revision_id,
            ),
        ),
    )
    completion = RegisteredOperationCompletion(
        operation_id=_OPERATION_ID,
        projection=projection,
        effect=OperationEffect.NONE,
    )
    requests = _bind(
        monkeypatch,
        completion=completion,
        definition_id=ACTIVITY_ASSET_INSPECT_OPERATION_DEFINITION_ID,
        request_type=ActivityAssetInspectRequest,
    )

    assert bridge.inspect_activity_asset(_context(), asset_id=revision.asset_id) is projection
    request = cast(ActivityAssetInspectRequest, requests[0])
    assert request.profile_id == _PROFILE
    assert request.asset_id == revision.asset_id
    revisions = projection.revisions
    if not revisions:
        raise AssertionError("inspect projection omitted its revision chain")
    assert revisions[0].revision.to_domain() == revision


def test_correct_bridge_sends_the_direct_successor_and_correlates_updated_history(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    initial = _revision()
    correction = _revision(number=2, supersedes=initial.revision_id)
    projection = ActivityAssetCorrectProjection(
        profile_id=_PROFILE,
        authority=_AUTHORITY,
        outcome="succeeded",
        history=ActivityAssetHistorySnapshot.from_domain(ActivityAssetHistory(revisions=(initial, correction))),
    )
    completion = RegisteredOperationCompletion(
        operation_id=_OPERATION_ID,
        projection=projection,
        effect=OperationEffect.UPDATED,
    )
    requests = _bind(
        monkeypatch,
        completion=completion,
        definition_id=ACTIVITY_ASSET_CORRECT_OPERATION_DEFINITION_ID,
        request_type=ActivityAssetCorrectRequest,
    )

    assert bridge.correct_activity_asset(_context(), revision=correction) is projection
    request = cast(ActivityAssetCorrectRequest, requests[0])
    assert request.profile_id == _PROFILE
    assert request.revision.to_domain() == correction
    history = projection.history
    if history is None:
        raise AssertionError("correction projection omitted its history")
    assert history.revisions[-1].to_domain() == correction


def test_forecast_bridge_preserves_dates_and_explicit_decimal_wire_fact(monkeypatch: pytest.MonkeyPatch) -> None:
    revision = _revision()
    schedule = _schedule(revision)
    projection = ActivityAssetForecastProjection(
        profile_id=_PROFILE,
        authority=_AUTHORITY,
        outcome="succeeded",
        forecast=ScheduledAmortizationChargeSnapshot.from_domain(schedule),
    )
    completion = RegisteredOperationCompletion(
        operation_id=_OPERATION_ID,
        projection=projection,
        effect=OperationEffect.NONE,
    )
    requests = _bind(
        monkeypatch,
        completion=completion,
        definition_id=ACTIVITY_ASSET_FORECAST_OPERATION_DEFINITION_ID,
        request_type=ActivityAssetForecastRequest,
    )

    assert (
        bridge.forecast_activity_asset(
            _context(),
            asset_id=revision.asset_id,
            covered_from=date(2025, 1, 1),
            covered_until=date(2026, 1, 1),
            requested_free_amount=Decimal("12.50"),
            supersedes_claim_id=None,
        )
        is projection
    )
    request = cast(ActivityAssetForecastRequest, requests[0])
    assert request.profile_id == _PROFILE
    assert request.asset_id == revision.asset_id
    assert request.covered_from == schedule.covered_from
    assert request.covered_until == schedule.covered_until
    assert request.requested_free_amount == PublicDecimal(decimal="12.50")


def test_claim_bridge_correlates_exact_claim_identity_and_update_effect(monkeypatch: pytest.MonkeyPatch) -> None:
    revision = _revision()
    schedule = _schedule(revision)
    claim = AmortizationClaim.from_schedule(
        schedule,
        asset_kind=revision.asset_kind,
        creating_operation="bridge.claim",
    )
    domain_result = ActivityAssetHistoryClaimResult(
        history=ActivityAssetHistory(revisions=(revision,), claims=(claim,)),
        claim=claim,
        reused_existing_claim=False,
    )
    projection = ActivityAssetClaimProjection(
        profile_id=_PROFILE,
        authority=_AUTHORITY,
        outcome="succeeded",
        claim_result=ActivityAssetHistoryClaimResultSnapshot.from_domain(domain_result),
        claim_id=claim.claim_id,
    )
    completion = RegisteredOperationCompletion(
        operation_id=_OPERATION_ID,
        projection=projection,
        effect=OperationEffect.UPDATED,
    )
    requests = _bind(
        monkeypatch,
        completion=completion,
        definition_id=ACTIVITY_ASSET_CLAIM_OPERATION_DEFINITION_ID,
        request_type=ActivityAssetClaimRequest,
    )

    assert (
        bridge.claim_activity_asset(
            _context(),
            forecast=schedule,
            creating_operation="bridge.claim",
            supersedes_claim_id=None,
        )
        is projection
    )
    request = cast(ActivityAssetClaimRequest, requests[0])
    assert request.profile_id == _PROFILE
    assert request.forecast.to_domain() == schedule
    assert request.creating_operation == "bridge.claim"
    claim_result = projection.claim_result
    if claim_result is None:
        raise AssertionError("claim projection omitted its claim result")
    assert claim_result.claim.to_domain() == claim


def test_filing_handoff_bridge_correlates_requested_frame_without_effect(monkeypatch: pytest.MonkeyPatch) -> None:
    projection_row = ClaimProjection(
        target_casilla_id="06",
        tax_year=2025,
        claim_ids=("c" * 64,),
        amount=Decimal("78.00"),
    )
    empty_row = projection_row.model_copy(
        update={"target_casilla_id": "07", "claim_ids": (), "amount": Decimal("0.00")}
    )
    handoff = ActivityAssetFilingHandoff(
        material_m100=projection_row,
        intangible_m100=empty_row,
        material_m130=projection_row,
        intangible_m130=empty_row,
    )
    projection = ActivityAssetFilingHandoffProjection(
        profile_id=_PROFILE,
        authority=_AUTHORITY,
        outcome="succeeded",
        tax_year=2025,
        m130_period="4T",
        filing_handoff=ActivityAssetFilingHandoffSnapshot.from_domain(handoff),
    )
    completion = RegisteredOperationCompletion(
        operation_id=_OPERATION_ID,
        projection=projection,
        effect=OperationEffect.NONE,
    )
    requests = _bind(
        monkeypatch,
        completion=completion,
        definition_id=ACTIVITY_ASSET_FILING_HANDOFF_OPERATION_DEFINITION_ID,
        request_type=ActivityAssetFilingHandoffRequest,
    )

    assert bridge.filing_handoff_activity_asset(_context(), tax_year=2025, m130_period="4T") is projection
    request = cast(ActivityAssetFilingHandoffRequest, requests[0])
    assert request.profile_id == _PROFILE
    assert (request.tax_year, request.m130_period) == (projection.tax_year, projection.m130_period)
    filing_handoff = projection.filing_handoff
    if filing_handoff is None:
        raise AssertionError("filing projection omitted its handoff")
    assert filing_handoff.to_domain() == handoff
