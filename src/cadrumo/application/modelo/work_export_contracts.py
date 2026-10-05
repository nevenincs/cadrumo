"""Local export request and exactly one settled export receipt."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from ...core.external_constants import OutputLanguage
from ...core.modelo_export_artefact import ModeloExportArtefact
from ...core.models import STRICT_FROZEN_CONFIG
from ...core.payment_election import PaymentElection
from ...core.prior_domiciliation_election import PriorDomiciliationElection
from ...core.refund_election import RefundElection
from ...domain.transactions.own_accounts import OwnAccountId
from ..operations.models import CredentialFreeOperationRequest
from .calculation_report_export import (
    ModeloCalculationReportResult,
)
from .export import ModeloExportResult


class ModeloExportRequest(CredentialFreeOperationRequest):
    """The revision to export, where the operator wants the artefact, and the elections that shape it.

    The path is the operator's chosen destination, journalled because it is a
    location rather than content. The exported bytes never enter the request
    or the result.

    The three elections are the declaration-shaping choices the command line
    also accepts, with the same neutral defaults, so one revision exports as
    the same declaration type from either surface.
    """

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid", validate_default=True)

    calculation_revision_id: Annotated[str, Field(min_length=1, max_length=128)]
    #: ``pattern=r"\S"`` refuses an all-whitespace destination, which
    #: ``min_length`` alone admits. NOT stripped: a path must stay byte-exact,
    #: and silently trimming one would mask a typo rather than surface it.
    output_path: Annotated[str, Field(min_length=1, max_length=4096, pattern=r"\S")]
    refund_election: RefundElection = RefundElection.COMPENSAR
    payment_election: PaymentElection = PaymentElection.INGRESO
    prior_domiciliation_election: PriorDomiciliationElection = PriorDomiciliationElection.KEEP
    #: Per-filing own-account choices by opaque register id; ``None`` resolves
    #: the register's designations. Account material never enters the request.
    charge_account_id: OwnAccountId | None = None
    refund_account_id: OwnAccountId | None = None
    #: Whether the operator chose to replace a file already at ``output_path``;
    #: without that choice an existing file refuses the export.
    replace_existing: bool = False
    #: Which artefact to publish. Defaults to the AEAT-compatible filing file, so
    #: a caller that names no artefact gets the export it always got; a
    #: calculation report is an explicit choice.
    artefact: ModeloExportArtefact = ModeloExportArtefact.FICHERO_BOE
    report_language: OutputLanguage = OutputLanguage.ES

    #: The operator this invocation acts as; stamped onto the exported
    #: artefact through the command built from this request.
    actor: Annotated[str, Field(min_length=1, max_length=128)]

    @model_validator(mode="after")
    def _absolute_output_path(self) -> Self:
        if not Path(self.output_path).is_absolute():
            raise ValueError("export output path must be resolved by the requesting frontend")
        return self


class ModeloExportSettledResult(BaseModel):
    """The export service's own receipt for one settled export, kept behind the secure operand boundary.

    Exactly one receipt is present: the filing file's or the calculation
    report's. The receipt is stored whole rather than as chosen fields, so the
    public result is a projection of the very object the command line renders
    and no surface re-derives a fact from anything else.
    """

    model_config = STRICT_FROZEN_CONFIG

    fichero_boe: ModeloExportResult | None = None
    calculation_report: ModeloCalculationReportResult | None = None

    @model_validator(mode="after")
    def _exactly_one_receipt(self) -> ModeloExportSettledResult:
        """Refuse a settlement naming no artefact, or two."""
        if (self.fichero_boe is None) == (self.calculation_report is None):
            raise ValueError("a settled export carries exactly one receipt")
        return self
