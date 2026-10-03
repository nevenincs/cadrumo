"""Activity-asset actions through one retained installed TUI session."""

from __future__ import annotations

import asyncio
from decimal import Decimal
from typing import NoReturn
from uuid import UUID

from pydantic import BaseModel

from ....adapters.local_runtime.frontend_client import RuntimeFrontendClient
from ....application.actividad_asset.history import ActivityAssetHistoryClaimResult
from ....application.actividad_asset.operation_dtos import (
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
    ActivityAssetInspectProjection,
    ActivityAssetInspectRequest,
)
from ....application.operations.frontend_projection import OperationPublicProjectionV1
from ....application.operations.public_scalar import PublicDecimal
from ....application.runtime.contracts import RuntimeRefusalCode, RuntimeRefusalError
from ....core.operations import (
    OperationEffect,
    OperationTerminalCondition,
)
from ....domain.renta.actividad_asset.claims import AmortizationClaim
from ....domain.renta.actividad_asset.schedule import ScheduledAmortizationCharge
from ..operations.runtime_profile_session import RuntimeProfileSession
from .actividad_asset import ActivityAssetTuiActionsV1
from .models_actividad_asset import (
    ActivityAssetClaimRequestV1,
    ActivityAssetCorrectionRequestV1,
    ActivityAssetCreationRequestV1,
    ActivityAssetFilingRequestV1,
    ActivityAssetForecastRequestV1,
    ActivityAssetInspectionV1,
)

type _ActivityAssetProjection = (
    ActivityAssetCreateProjection
    | ActivityAssetInspectProjection
    | ActivityAssetCorrectProjection
    | ActivityAssetForecastProjection
    | ActivityAssetClaimProjection
    | ActivityAssetFilingHandoffProjection
)


def _activity_asset_success_effect(
    projection: _ActivityAssetProjection,
    success_effect: OperationEffect,
) -> OperationEffect:
    if projection.outcome == "refused":
        return OperationEffect.NONE
    if (
        isinstance(projection, ActivityAssetClaimProjection)
        and projection.claim_result is not None
        and projection.claim_result.reused_existing_claim
    ):
        return OperationEffect.NONE
    return success_effect


def _activity_asset_refusal_matches(
    projection: _ActivityAssetProjection,
    *,
    refused: bool,
    refusal_code: str | None,
) -> bool:
    result_refusal = projection.refusal
    if refused != (result_refusal is not None):
        return False
    result_code = result_refusal.code if result_refusal is not None else None
    return refusal_code == result_code


class RuntimeActivityAssetTuiActionsV1:
    """Submit exact-profile activity-asset requests to the installed runtime."""

    def __init__(self, client: RuntimeFrontendClient, *, profile_label: str) -> None:
        """Retain the originating TUI client, profile and session for every call."""
        self._session = RuntimeProfileSession(client, profile_label=profile_label)
        self._profile_id = self._session.profile_id

    def _call[ProjectionT: _ActivityAssetProjection](
        self,
        request: BaseModel,
        *,
        definition_id: str,
        result_type: type[ProjectionT],
        success_effect: OperationEffect,
    ) -> ProjectionT:
        """Run one registered operation from the screen's background worker."""

        def settle(
            projection: ProjectionT,
            condition: OperationTerminalCondition,
            terminal: OperationPublicProjectionV1,
            operation_id: str,
        ) -> None:
            self._validate_terminal_result(
                projection,
                profile_id=self._profile_id,
                terminal_condition=condition,
                effect=terminal.effect,
                refusal_code=terminal.refusal_ref,
                success_effect=success_effect,
            )
            if projection.outcome == "refused":
                self._raise_refusal(
                    projection,
                    operation_id=operation_id,
                    terminal_condition=condition,
                    effect=terminal.effect,
                )

        return asyncio.run(
            self._session.run_operation(
                request,
                definition_id=definition_id,
                result_type=result_type,
                settle=settle,
                allow_refusal_detail=True,
            )
        )

    @staticmethod
    def _validate_terminal_result(
        projection: _ActivityAssetProjection,
        *,
        profile_id: UUID,
        terminal_condition: OperationTerminalCondition,
        effect: OperationEffect,
        refusal_code: str | None,
        success_effect: OperationEffect,
    ) -> None:
        """Correlate the typed result with its authoritative terminal receipt."""
        if projection.profile_id != profile_id or not isinstance(
            projection.authority, ActivityAssetAuthorityProvenance
        ):
            raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
        refused = projection.outcome == "refused"
        expected_condition = OperationTerminalCondition.REFUSED if refused else OperationTerminalCondition.SUCCEEDED
        expected_effect = _activity_asset_success_effect(projection, success_effect)
        if (
            terminal_condition is not expected_condition
            or effect is not expected_effect
            or not _activity_asset_refusal_matches(projection, refused=refused, refusal_code=refusal_code)
        ):
            raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)

    @staticmethod
    def _raise_refusal(
        projection: _ActivityAssetProjection,
        *,
        operation_id: str,
        terminal_condition: OperationTerminalCondition,
        effect: OperationEffect,
    ) -> NoReturn:
        """Rebuild the established domain refusal with the settled receipt."""
        refusal = projection.refusal
        if refusal is None:
            raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
        context: dict[str, object] = {
            "operation_id": operation_id,
            "terminal_condition": terminal_condition.value,
            "effect": effect.value,
            "refusal_code": refusal.code,
        }
        raise refusal.to_domain_error(context=context)

    def create(self, request: ActivityAssetCreationRequestV1) -> ActivityAssetInspectionV1:
        """Create an asset and return its complete persisted revision chain."""
        projection = self._call(
            ActivityAssetCreateRequest(
                profile_id=self._profile_id,
                revision=ActivityAssetRevisionSnapshot.from_domain(request.revision),
            ),
            definition_id=ACTIVITY_ASSET_CREATE_OPERATION_DEFINITION_ID,
            result_type=ActivityAssetCreateProjection,
            success_effect=OperationEffect.UPDATED,
        )
        if projection.history is None:
            raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
        return self._inspection_from_history(projection.history, request.revision.asset_id)

    def inspect(self, asset_id: str) -> ActivityAssetInspectionV1:
        """Read one complete immutable revision chain through the runtime."""
        projection = self._call(
            ActivityAssetInspectRequest(profile_id=self._profile_id, asset_id=asset_id),
            definition_id=ACTIVITY_ASSET_INSPECT_OPERATION_DEFINITION_ID,
            result_type=ActivityAssetInspectProjection,
            success_effect=OperationEffect.NONE,
        )
        if projection.asset_id != asset_id or projection.revisions is None:
            raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
        return ActivityAssetInspectionV1(
            asset_id=asset_id,
            revisions=tuple(item.revision.to_domain() for item in projection.revisions),
        )

    def correct(self, request: ActivityAssetCorrectionRequestV1) -> ActivityAssetInspectionV1:
        """Append a correction and return the complete persisted revision chain."""
        projection = self._call(
            ActivityAssetCorrectRequest(
                profile_id=self._profile_id,
                revision=ActivityAssetRevisionSnapshot.from_domain(request.revision),
            ),
            definition_id=ACTIVITY_ASSET_CORRECT_OPERATION_DEFINITION_ID,
            result_type=ActivityAssetCorrectProjection,
            success_effect=OperationEffect.UPDATED,
        )
        if projection.history is None:
            raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
        return self._inspection_from_history(projection.history, request.revision.asset_id)

    def forecast(self, request: ActivityAssetForecastRequestV1) -> ScheduledAmortizationCharge:
        """Return the full typed schedule produced by the pinned worker."""
        projection = self._call(
            ActivityAssetForecastRequest(
                profile_id=self._profile_id,
                asset_id=request.asset_id,
                covered_from=request.covered_from,
                covered_until=request.covered_until,
                requested_free_amount=(
                    None
                    if request.requested_free_amount is None
                    else self._public_decimal(request.requested_free_amount)
                ),
                supersedes_claim_id=request.supersedes_claim_id,
            ),
            definition_id=ACTIVITY_ASSET_FORECAST_OPERATION_DEFINITION_ID,
            result_type=ActivityAssetForecastProjection,
            success_effect=OperationEffect.NONE,
        )
        if projection.forecast is None:
            raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
        forecast = projection.forecast.to_domain()
        if (
            forecast.asset_id != request.asset_id
            or forecast.covered_from != request.covered_from
            or forecast.covered_until != request.covered_until
        ):
            raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
        return forecast

    def record_claim(self, request: ActivityAssetClaimRequestV1) -> ActivityAssetHistoryClaimResult:
        """Commit or replay the exact supplied forecast through the worker."""
        projection = self._call(
            ActivityAssetClaimRequest(
                profile_id=self._profile_id,
                forecast=ScheduledAmortizationChargeSnapshot.from_domain(request.forecast),
                creating_operation=request.creating_operation,
                supersedes_claim_id=request.supersedes_claim_id,
            ),
            definition_id=ACTIVITY_ASSET_CLAIM_OPERATION_DEFINITION_ID,
            result_type=ActivityAssetClaimProjection,
            success_effect=OperationEffect.UPDATED,
        )
        if projection.claim_result is None or projection.claim_id is None:
            raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
        claim_result = projection.claim_result.to_domain()
        revision = next(
            (item for item in claim_result.history.revisions if item.revision_id == request.forecast.asset_revision_id),
            None,
        )
        if revision is None:
            raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
        expected_claim = AmortizationClaim.from_schedule(
            request.forecast,
            asset_kind=revision.asset_kind,
            creating_operation=request.creating_operation,
            supersedes_claim_id=request.supersedes_claim_id,
        )
        if projection.claim_id != expected_claim.claim_id or claim_result.claim != expected_claim:
            raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
        return claim_result

    def filing_handoff(self, request: ActivityAssetFilingRequestV1) -> ActivityAssetFilingHandoff:
        """Return all four exact M100/M130 projections from the worker result."""
        projection = self._call(
            ActivityAssetFilingHandoffRequest(
                profile_id=self._profile_id,
                tax_year=int(request.tax_year),
                m130_period=str(request.m130_period.code),
            ),
            definition_id=ACTIVITY_ASSET_FILING_HANDOFF_OPERATION_DEFINITION_ID,
            result_type=ActivityAssetFilingHandoffProjection,
            success_effect=OperationEffect.NONE,
        )
        if (
            projection.filing_handoff is None
            or projection.tax_year != request.tax_year
            or projection.m130_period != str(request.m130_period.code)
        ):
            raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
        return projection.filing_handoff.to_domain()

    @staticmethod
    def _inspection_from_history(snapshot: ActivityAssetHistorySnapshot, asset_id: str) -> ActivityAssetInspectionV1:
        """Preserve the complete per-asset immutable history in the UI result."""
        history = snapshot.to_domain()
        revisions = tuple(item for item in history.revisions if item.asset_id == asset_id)
        if not revisions:
            raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
        return ActivityAssetInspectionV1(asset_id=asset_id, revisions=revisions)

    @staticmethod
    def _public_decimal(value: Decimal) -> PublicDecimal:
        """Use the registered bounded decimal wire type without float coercion."""
        return PublicDecimal(decimal=str(value))


def compose_runtime_activity_asset_actions(
    client: RuntimeFrontendClient, *, profile_label: str
) -> ActivityAssetTuiActionsV1:
    """Bind the current Ledger screen to one admitted profile/session runtime."""
    return RuntimeActivityAssetTuiActionsV1(client, profile_label=profile_label)


__all__ = ["RuntimeActivityAssetTuiActionsV1", "compose_runtime_activity_asset_actions"]
