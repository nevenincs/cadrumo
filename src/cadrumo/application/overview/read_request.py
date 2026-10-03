"""Canonical query input and command vocabulary for overview reads."""

from __future__ import annotations

from datetime import date
from enum import StrEnum
from typing import Self
from uuid import UUID

from pydantic import Field, model_validator

from ...core.external_constants import OutputLanguage
from ...core.filing_year import FilingYear
from ..operations.models import CredentialFreeOperationRequest
from ..operations.public_period import PublicPeriod


class OverviewReadKind(StrEnum):
    """Installed read leaves sharing the same authenticated capture seam."""

    STATUS = "status"
    CALENDAR = "calendar"
    AGENDA = "agenda"
    BACKLOG = "backlog"
    EXPLAIN = "explain"
    PREPARE = "prepare"


OVERVIEW_READ_DEFINITION_IDS = {kind: f"overview.{kind.value}" for kind in OverviewReadKind}


class OverviewReadRequest(CredentialFreeOperationRequest):
    """One immutable query, with irrelevant fields structurally refused."""

    profile_id: UUID
    kind: OverviewReadKind
    output_language: OutputLanguage
    period: PublicPeriod | None = None
    from_date: date | None = None
    to_date: date | None = None
    as_of: date | None = None
    horizon_days: int | None = None
    modelo: str | None = Field(default=None, pattern=r"^[0-9]{3}$", max_length=3)
    year: FilingYear | None = None
    verbose: bool | None = None
    allow_incomplete: bool | None = None
    show_suppressed: bool | None = None
    all_profiles: bool | None = None

    @model_validator(mode="after")
    def _query(self) -> Self:
        _reject_irrelevant_query_fields(self)
        _validate_query_date_window(self)
        _validate_query_scope(self)
        _validate_query_horizon(self)
        return self


def _reject_irrelevant_query_fields(request: OverviewReadRequest) -> None:
    common = {"profile_id", "kind", "output_language"}
    allowed = {
        OverviewReadKind.STATUS: {"period", "verbose"},
        OverviewReadKind.CALENDAR: {"from_date", "to_date", "allow_incomplete", "show_suppressed", "all_profiles"},
        OverviewReadKind.AGENDA: {"as_of", "horizon_days", "allow_incomplete"},
        OverviewReadKind.BACKLOG: {"from_date", "to_date", "allow_incomplete"},
        OverviewReadKind.EXPLAIN: {"modelo", "year"},
        OverviewReadKind.PREPARE: {"modelo", "period"},
    }[request.kind]
    irrelevant = type(request).model_fields.keys() - common - allowed
    if any(getattr(request, field) is not None for field in irrelevant):
        raise ValueError("overview query contains fields from another command")


def _validate_query_date_window(request: OverviewReadRequest) -> None:
    if request.kind is OverviewReadKind.CALENDAR and (request.from_date is None or request.to_date is None):
        raise ValueError("calendar query requires a date window")
    if request.from_date is not None and request.to_date is not None and request.from_date > request.to_date:
        raise ValueError("overview date window is reversed")


def _validate_query_scope(request: OverviewReadRequest) -> None:
    if request.kind in {OverviewReadKind.EXPLAIN, OverviewReadKind.PREPARE} and not request.modelo:
        raise ValueError("overview query requires a modelo")
    if request.kind is OverviewReadKind.PREPARE and request.period is None:
        raise ValueError("preparation query requires an exact period")


def _validate_query_horizon(request: OverviewReadRequest) -> None:
    if request.horizon_days is not None and not 1 <= request.horizon_days <= 365:
        raise ValueError("agenda horizon must be between one and 365 days")


__all__ = ["OVERVIEW_READ_DEFINITION_IDS", "OverviewReadKind", "OverviewReadRequest"]
