"""Settled verification report and application advisory contracts."""

from __future__ import annotations

from typing import Annotated, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, NonNegativeInt, model_validator

from ...core.models import STRICT_FROZEN_CONFIG
from ..operations.models import CredentialFreeOperationRequest
from .lifecycle_advisories import ModeloLifecycleAdvisories
from .verification_projection import ModeloVerificationReportSnapshot, ModeloVerificationSnapshot


class ModeloWorkVerifyRequest(CredentialFreeOperationRequest):
    """The calculation revision to verify.

    The taxpayer profile the gates are evaluated against is deliberately NOT
    carried here. It is resolved at execution from live state, so a request
    replayed later cannot verify against a profile the taxpayer has since
    changed.
    """

    model_config = STRICT_FROZEN_CONFIG

    calculation_revision_id: Annotated[str, Field(min_length=1, max_length=128, pattern=r"\S")]

    #: The operator this invocation acts as. The platform binds an actor at
    #: submission, never at composition, so baking one into a definition would
    #: make the production registry per-actor.
    actor: Annotated[str, Field(min_length=1, max_length=128, pattern=r"\S")]


def _verification_summary_differs(
    result: ModeloWorkVerifyPublicResultV2, report: ModeloVerificationReportSnapshot
) -> bool:
    return (
        result.verification_report_id != report.verification_report_id
        or result.calculation_revision_id != report.calculation_revision_id
        or result.completeness_status != report.completeness_status.value
        or result.granted_verificado_completo != report.granted_verificado_completo
        or result.finding_count != len(report.findings)
        or result.missing_required_casilla_count != len(report.missing_required_casilla_ids)
    )


def _verification_advisories_differ(
    result: ModeloWorkVerifyPublicResultV2, report: ModeloVerificationReportSnapshot
) -> bool:
    return (
        result.advisories.calculation_revision_id != report.calculation_revision_id
        or result.advisories.modelo != report.registry_snapshot_ref.modelo
        or result.advisories.filing_year != report.registry_snapshot_ref.modelo_year
        or result.advisories.period != report.registry_snapshot_ref.period
    )


class ModeloWorkVerifyPublicResultV2(BaseModel):
    """The settled report and application findings for authorized presentation."""

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid", validate_default=True)

    result_version: Literal[2] = 2
    verification: ModeloVerificationSnapshot
    advisories: ModeloLifecycleAdvisories
    verification_report_id: Annotated[str, Field(min_length=1, max_length=128)]
    calculation_revision_id: Annotated[str, Field(min_length=1, max_length=128)]
    completeness_status: Annotated[str, Field(min_length=1, max_length=64)]
    granted_verificado_completo: bool
    finding_count: NonNegativeInt
    missing_required_casilla_count: NonNegativeInt

    @model_validator(mode="after")
    def _report_summary(self) -> Self:
        report = self.verification.report
        if _verification_summary_differs(self, report) or _verification_advisories_differ(self, report):
            raise ValueError("verification summary does not match its persisted report")
        return self
