"""Canonical captured result and authorized projection for overview reads."""

from __future__ import annotations

from typing import Self
from uuid import UUID

from pydantic import BaseModel, model_validator

from ...core.models import STRICT_FROZEN_HIDDEN_INPUT_CONFIG
from ...core.operations import OperationEffect, OperationTerminalCondition, profile_operation_subject
from ..operations.models import OperationTerminalReceipt, require_terminal_receipt_match
from .read_payload import (
    OverviewAgendaRead,
    OverviewCalendarRead,
    OverviewExplainRead,
    OverviewPrepareRead,
    OverviewReadPayload,
    OverviewStatusRead,
)
from .read_request import OVERVIEW_READ_DEFINITION_IDS, OverviewReadRequest


def _validate_result(profile_id: UUID, request: OverviewReadRequest, payload: OverviewReadPayload) -> None:
    if request.profile_id != profile_id or payload.kind != request.kind.value:
        raise ValueError("overview read identity differs from its request")
    if isinstance(payload, OverviewStatusRead):
        _validate_status_result(request, payload)
    elif isinstance(payload, OverviewCalendarRead):
        _validate_calendar_result(profile_id, request, payload)
    elif isinstance(payload, OverviewAgendaRead):
        _validate_agenda_result(request, payload)
    elif isinstance(payload, OverviewExplainRead):
        _validate_explain_result(request, payload)
    elif isinstance(payload, OverviewPrepareRead):
        _validate_prepare_result(request, payload)


def _validate_status_result(request: OverviewReadRequest, payload: OverviewStatusRead) -> None:
    if (payload.period_report is None) != (request.period is None):
        raise ValueError("overview status scope differs from its request")
    if payload.period_report is not None and payload.period_report.period != request.period:
        raise ValueError("overview period status differs from requested period")


def _validate_calendar_result(profile_id: UUID, request: OverviewReadRequest, payload: OverviewCalendarRead) -> None:
    _validate_calendar_profile_mode(request, payload)
    _validate_calendar_window(request, payload)
    _validate_survey_window(request, payload)
    _validate_survey_profile(profile_id, payload)


def _validate_calendar_profile_mode(request: OverviewReadRequest, payload: OverviewCalendarRead) -> None:
    if (payload.survey is not None) != bool(request.all_profiles):
        raise ValueError("overview calendar profile mode differs from request")


def _validate_calendar_window(request: OverviewReadRequest, payload: OverviewCalendarRead) -> None:
    calendar = payload.calendar
    if calendar is None and payload.survey is not None:
        calendar = payload.survey.active_calendar
    if calendar is not None and (
        calendar.range.from_date != request.from_date or calendar.range.to_date != request.to_date
    ):
        raise ValueError("overview calendar window differs from request")


def _validate_survey_window(request: OverviewReadRequest, payload: OverviewCalendarRead) -> None:
    if payload.survey is not None and (
        payload.survey.from_date != request.from_date or payload.survey.to_date != request.to_date
    ):
        raise ValueError("overview survey window differs from request")


def _validate_survey_profile(profile_id: UUID, payload: OverviewCalendarRead) -> None:
    if payload.survey is not None and payload.survey.active_profile_id not in {None, str(profile_id)}:
        raise ValueError("overview survey exposed another active profile")


def _validate_agenda_result(request: OverviewReadRequest, payload: OverviewAgendaRead) -> None:
    if request.as_of is not None and payload.agenda.as_of != request.as_of:
        raise ValueError("overview agenda date differs from request")
    if request.horizon_days is not None and payload.agenda.horizon_days != request.horizon_days:
        raise ValueError("overview agenda horizon differs from request")


def _validate_explain_result(request: OverviewReadRequest, payload: OverviewExplainRead) -> None:
    if payload.explanation.modelo != request.modelo or (
        request.year is not None and payload.explanation.year != request.year
    ):
        raise ValueError("overview explanation differs from request")


def _validate_prepare_result(request: OverviewReadRequest, payload: OverviewPrepareRead) -> None:
    if (
        payload.preparation.modelo != request.modelo
        or request.period is None
        or payload.preparation.filing_year != request.period.filing_year
        or payload.preparation.period != request.period.code
    ):
        raise ValueError("overview preparation differs from requested scope")


class OverviewReadResult(BaseModel):
    """Encrypted canonical capture with immutable request provenance."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    profile_id: UUID
    request: OverviewReadRequest
    payload: OverviewReadPayload

    @model_validator(mode="after")
    def _scope(self) -> Self:
        _validate_result(self.profile_id, self.request, self.payload)
        return self


class OverviewReadProjection(BaseModel):
    """Independent result disclosure with only closed captured facts."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    profile_id: UUID
    request: OverviewReadRequest
    payload: OverviewReadPayload

    @model_validator(mode="after")
    def _scope(self) -> Self:
        _validate_result(self.profile_id, self.request, self.payload)
        return self


def project_overview_read_result(result: BaseModel, receipt: OperationTerminalReceipt, /) -> OverviewReadProjection:
    """Release only a successful no-effect result for its exact profile subject."""
    if type(result) is not OverviewReadResult:
        raise ValueError("invalid overview read result")
    private = OverviewReadResult.model_validate(result.model_dump(mode="python"), strict=True)
    require_terminal_receipt_match(
        receipt,
        definition_id=OVERVIEW_READ_DEFINITION_IDS[private.request.kind],
        subject_ref=profile_operation_subject(str(private.profile_id)),
        condition=OperationTerminalCondition.SUCCEEDED,
        effect=OperationEffect.NONE,
        message="overview read result contradicts its terminal receipt",
    )
    return OverviewReadProjection(profile_id=private.profile_id, request=private.request, payload=private.payload)


__all__ = ["OverviewReadProjection", "OverviewReadResult", "project_overview_read_result"]
