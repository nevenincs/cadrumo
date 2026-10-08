"""Exact approval, request and committed record contracts for modelo filing."""

from __future__ import annotations

from typing import Annotated, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from ...core.payment_election import PaymentElection
from ...core.prior_domiciliation_election import PriorDomiciliationElection
from ...core.refund_election import RefundElection
from ..operations.models import CredentialFreeOperationRequest
from .filing_projection import ModeloFilingRecordSnapshot
from .lifecycle_advisories import ModeloLifecycleAdvisories
from .work_change_contracts import ModeloWorkUnitSubjectId


class ModeloWorkFileApproval(BaseModel):
    """The exact verified revision an operator approved for local filing.

    Filing is a durable declaration of what the taxpayer intends to submit, so
    approval names the revision AND the verification that justified it. A
    revision re-verified since approval is a different fact, and filing it on
    the strength of the older look would record an intent nobody formed.
    """

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid", validate_default=True)

    calculation_revision_id: Annotated[str, Field(min_length=1, max_length=128)]
    verification_report_id: Annotated[str, Field(min_length=1, max_length=128)]


class ModeloWorkFileRequest(CredentialFreeOperationRequest):
    """The approved revision and the operator's declared election choices."""

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid", validate_default=True)

    approval: ModeloWorkFileApproval
    refund_election: RefundElection = RefundElection.COMPENSAR
    payment_election: PaymentElection = PaymentElection.INGRESO
    prior_domiciliation_election: PriorDomiciliationElection = PriorDomiciliationElection.KEEP
    notes: Annotated[str, Field(min_length=1, max_length=500)] | None = None

    #: The operator this invocation acts as. The platform binds an actor at
    #: submission, never at composition, so baking one into a definition would
    #: make the production registry per-actor.
    actor: Annotated[str, Field(min_length=1, max_length=128)]


class ModeloWorkFilePublicResultV2(BaseModel):
    """The recorded local filing, as a caller outside this package may see it.

    ``handoff_required`` is always true and is part of the contract, not a
    computed field: this operation records a filing locally and hands the
    operator the artefacts to submit themselves. Nothing here reaches AEAT.
    """

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid", validate_default=True)

    result_version: Literal[2] = 2
    record: ModeloFilingRecordSnapshot
    advisories: ModeloLifecycleAdvisories
    published: bool
    filing_record_id: Annotated[str, Field(min_length=1, max_length=128)]
    work_unit_id: ModeloWorkUnitSubjectId
    calculation_revision_id: Annotated[str, Field(min_length=1, max_length=128)]
    handoff_required: Literal[True] = True

    @model_validator(mode="after")
    def _record_summary(self) -> Self:
        if (
            self.filing_record_id != self.record.filing_record_id
            or self.work_unit_id != self.record.work_unit_id
            or self.calculation_revision_id != self.record.calculation_revision_id
            or self.advisories.calculation_revision_id != self.calculation_revision_id
            or self.advisories.work_unit_id != self.work_unit_id
            or self.advisories.modelo != self.record.modelo
            or self.advisories.filing_year != self.record.filing_year
            or self.advisories.period != self.record.period.to_period().registry_token
        ):
            raise ValueError("filing summary does not match its committed record")
        return self
