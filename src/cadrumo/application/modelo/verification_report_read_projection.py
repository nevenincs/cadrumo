"""Bounded report-list and exact-report view projections."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal, Self
from uuid import UUID

from pydantic import BaseModel, Field, NonNegativeInt, model_validator

from ...core.identity.hex_ids import CalculationRevisionId, VerificationReportId
from ...core.models import STRICT_FROZEN_HIDDEN_INPUT_CONFIG
from .verification_report_public_facts import ModeloVerificationReportProjection
from .verification_report_read_contracts import MAX_MODELO_VERIFICATION_REPORT_LIST_ROWS


def _projection_order_key(report: ModeloVerificationReportProjection) -> tuple[str, datetime]:
    return report.calculation_revision_id, report.run_at


class ModeloVerificationReportListProjection(BaseModel):
    """Complete, ordered report history captured for one exact profile."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    result_version: Literal[1] = 1
    profile_id: UUID
    calculation_revision_id_filter: CalculationRevisionId | None
    report_count: NonNegativeInt
    reports: Annotated[
        tuple[ModeloVerificationReportProjection, ...], Field(max_length=MAX_MODELO_VERIFICATION_REPORT_LIST_ROWS)
    ]

    @model_validator(mode="after")
    def _correlate_reports(self) -> Self:
        if self.report_count != len(self.reports):
            raise ValueError("verification report count does not match its rows")
        if any(
            self.calculation_revision_id_filter is not None
            and report.calculation_revision_id != self.calculation_revision_id_filter
            for report in self.reports
        ):
            raise ValueError("verification report list exceeds its calculation revision filter")
        if len({report.verification_report_id for report in self.reports}) != len(self.reports):
            raise ValueError("verification report list repeats an identity")
        if self.reports != tuple(sorted(self.reports, key=_projection_order_key)):
            raise ValueError("verification report list is not in the established order")
        return self


class ModeloVerificationReportViewProjection(BaseModel):
    """One report bound to the requested profile and report identity."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    result_version: Literal[1] = 1
    profile_id: UUID
    verification_report_id: VerificationReportId
    report: ModeloVerificationReportProjection

    @model_validator(mode="after")
    def _correlate_report(self) -> Self:
        if self.report.verification_report_id != self.verification_report_id:
            raise ValueError("verification report view does not match the requested identity")
        return self
