"""Resolve the pinned filing and provider access needed by spreadsheet operations."""

from __future__ import annotations

from dataclasses import replace

from pydantic import BaseModel

from ...core.capabilities import ServiceCapability
from ...core.period import Period
from ...domain.calculations.registry.relations import relation_source_requirements
from ...domain.calculations.registry.schema import RegistrySnapshot
from ..ledger.read_access import resolve_ledger_read_access
from ..operations.access_resolution import OperationAccessContext, ResolvedOperationAccess
from ..operations.models import OperationRequest
from ..operations.profile_guard import require_access_request_profile_payload
from ..user_profile.access_contracts import AccessAction, AccessDenialCode, Availability, OperationAccessPolicy
from ..user_profile.access_errors import ProfileAccessRefusedError
from ..user_profile.capabilities import resolve_active_capability
from .modelo_spreadsheet_operation_contracts import (
    MODELO_SPREADSHEET_OPERATION_CONTRACTS,
    ModeloSpreadsheetExportRequest,
    ModeloSpreadsheetRequest,
    ModeloSpreadsheetVerifyRequest,
)


def _admitted_access_payload(
    request: OperationRequest[BaseModel], context: OperationAccessContext
) -> ModeloSpreadsheetRequest:
    pair = MODELO_SPREADSHEET_OPERATION_CONTRACTS.get(request.definition_id)
    if pair is None:
        raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
    return require_access_request_profile_payload(
        request,
        definition_id=request.definition_id,
        payload_type=pair[0],
        access_profile_id=context.profile_id,
    )


def _source_periods(
    payload: ModeloSpreadsheetRequest, *, period: Period, snapshot: RegistrySnapshot
) -> frozenset[Period]:
    periods = {period}
    if not isinstance(payload, ModeloSpreadsheetExportRequest) or not payload.prefill_relations:
        return frozenset(periods)
    for requirement in relation_source_requirements(
        snapshot.revision, filing_year=snapshot.filing_year, period=snapshot.period
    ):
        # Keep canonical filing-period identities, with the established registry fallback.
        source_periods = requirement.filing_periods or tuple(
            Period.from_year_and_code(requirement.filing_year, code) for code in requirement.periods
        )
        periods.update(source_periods)
    return frozenset(periods)


def _spreadsheet_provider(payload: ModeloSpreadsheetRequest) -> Availability:
    if not isinstance(payload, ModeloSpreadsheetVerifyRequest):
        return Availability.NOT_REQUIRED
    return (
        Availability.AVAILABLE
        if resolve_active_capability(ServiceCapability.GOOGLE_EXPORT).enabled
        else Availability.UNAVAILABLE
    )


def resolve_modelo_spreadsheet_access(
    request: OperationRequest[BaseModel], context: OperationAccessContext, /
) -> ResolvedOperationAccess:
    """Resolve filing and relation-source periods from the retained published pin."""
    payload = _admitted_access_payload(request, context)
    operation = context.authority_operation
    if operation is None:
        raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
    period = payload.period.to_period()
    snapshot = operation.snapshot(payload.modelo, filing_year=period.filing_year, period=period.registry_token)
    periods = _source_periods(payload, period=period, snapshot=snapshot)
    resolved = resolve_ledger_read_access(request, context, profile_id=payload.profile_id, periods=periods)
    policy = OperationAccessPolicy.model_validate(
        {
            **dict(resolved.policy),
            "actions": resolved.policy.actions | {AccessAction.COMMIT},
            "provider": _spreadsheet_provider(payload),
        }
    )
    return replace(resolved, policy=policy)


__all__ = ["resolve_modelo_spreadsheet_access"]
